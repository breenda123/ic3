# quiz_api/urls.py
from django.urls import path

from .views import (
    ModuleListView,
    QuestionTypeListView,
    QuestionListCreateView,
    QuestionRetrieveUpdateDestroyView,
    QuestionUploadView,
    frontend_view,
)

urlpatterns = [
    path('', frontend_view, name='frontend-home'), # URL gốc cho frontend
    path('modules/', ModuleListView.as_view(), name='module-list'),
    path('question-types/', QuestionTypeListView.as_view(), name='question-type-list'),
    path('questions/', QuestionListCreateView.as_view(), name='question-list-create'),
    path('questions/<int:pk>/', QuestionRetrieveUpdateDestroyView.as_view(), name='question-detail'),
    path('questions/upload/', QuestionUploadView.as_view(), name='question-upload'),
]
