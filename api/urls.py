from django.urls import path , include

app_name = "api"

urlpatterns = [
    path("",include("api.apis.v1.urls",namespace="apis_v1")),
]