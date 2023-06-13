from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required

from onlinecourse.models import Course, Enrollment, Question, Choice, Submission

import logging


# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == "GET":
        return render(request, "onlinecourse/user_registration_bootstrap.html", context)
    elif request.method == "POST":
        # Check if user exists
        username = request.POST["username"]
        password = request.POST["psw"]
        first_name = request.POST["firstname"]
        last_name = request.POST["lastname"]
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password,
            )
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context["message"] = "User already exists."
            return render(
                request, "onlinecourse/user_registration_bootstrap.html", context
            )


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["psw"]
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context["message"] = "Invalid username or password."
            return render(request, "onlinecourse/user_login_bootstrap.html", context)
    else:
        return render(request, "onlinecourse/user_login_bootstrap.html", context)


def logout_request(request):
    logout(request)
    return redirect("onlinecourse:index")


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = "onlinecourse/course_list_bootstrap.html"
    context_object_name = "course_list"

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by("-total_enrollment")[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = "onlinecourse/course_detail_bootstrap.html"


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode="honor")
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse(viewname="onlinecourse:course_details", args=(course.id,))
    )


def submit_exam(request, course_id):
    user = request.user
    course = get_object_or_404(Course, pk=course_id)
    enrollment = get_object_or_404(Enrollment, user=user, course=course)

    if request.method == 'POST':
        submission = Submission.objects.create(enrollment=enrollment)

        selected_choice_ids = request.POST.getlist('selected_choices')
        selected_choices = Choice.objects.filter(id__in=selected_choice_ids)

        submission.selected_choices.set(selected_choices)  # Add selected choices to submission object

        return redirect('onlinecourse:show_exam_result', course_id=course.id, submission_id=submission.id)
    else:
        return redirect('onlinecourse:course_details', pk=course_id)


def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)
    total_score = 0
    question_results = {}

    def is_answer_correct(question, selected_ids):
        all_answers = question.choices.filter(is_correct=True).count()
        selected_correct = question.choices.filter(is_correct=True, id__in=selected_ids).count()
        return all_answers == selected_correct

    submitted_choice_ids = request.POST.getlist('choices')

    # Loop through all questions in the course
    for question in course.questions.all():
        # Get the selected ids for this question
        selected_ids = [int(choice_id) for choice_id in submitted_choice_ids if choice_id.startswith(str(question.id))]

        # Check if the answer is correct
        is_correct = is_answer_correct(question, selected_ids)
        question_results[question] = is_correct

        if is_correct:
            total_score += question.grade

    context = {
        "course_id": course_id,
        "total_score": total_score,
        "question_results": question_results,
        "submission_id": submission_id,
    }
    return render(request, "onlinecourse/exam_result_bootstrap.html", context)
