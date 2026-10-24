from django.urls import path

from . import views

# include() this at the path thumbnails should be served from, e.g.
# path("thumb/", include("opposable_thumbs.django.urls"))
app_name = "opposable_thumbs"
urlpatterns = [path("", views.thumbnail, name="thumbnail")]
