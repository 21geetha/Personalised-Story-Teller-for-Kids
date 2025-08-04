from django.urls import path
from .views import login_view, register_view,story_form,logout_view,home_view,choose_story,view_story,view_translated_story

urlpatterns = [
    path('', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('home/', home_view, name='home'), 
    path('story/', story_form, name='story_form'),
    path('logout/',logout_view,name='logout'),
    path('choose/', choose_story, name='choose_story'),
    path('story/<int:story_id>/', view_story, name='view_story'),
    path('translate-story/', view_translated_story, name='view_translated_story'),
]
