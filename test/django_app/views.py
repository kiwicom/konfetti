from django.conf import settings
from django.conf.urls import url
from django.http import HttpResponse, JsonResponse


def index(request):
    return JsonResponse(settings.asdict())


def ping(request):
    return HttpResponse("OK")


urlpatterns = (url(r"^$", index), url(r"^ping$", ping))
