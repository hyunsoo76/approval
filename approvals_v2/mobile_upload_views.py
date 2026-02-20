from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import TempUploadImage
import uuid

def mobile_upload_page(request, token):
    return render(request, "approvals_v2/mobile_upload.html", {"token": token})

@csrf_exempt
def mobile_upload_api(request, token):
    if request.method == "POST" and request.FILES.get("image"):
        TempUploadImage.objects.create(
            token=token,
            image=request.FILES["image"]
        )
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False})

def mobile_upload_poll(request, token):
    img = TempUploadImage.objects.filter(token=token, is_used=False).first()
    if img:
        img.is_used = True
        img.save()
        return JsonResponse({
            "image_url": img.image.url
        })
    return JsonResponse({"image_url": None})
