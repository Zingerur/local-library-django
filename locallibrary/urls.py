from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Адмін-панель Django
    path('admin/', admin.site.urls),

    # Підключаємо URL-и додатку catalog
    path('catalog/', include('catalog.urls')),

    # Редірект з головної сторінки сайту на /catalog/
    path('', RedirectView.as_view(url='catalog/', permanent=True)),
]

# Обслуговування статичних файлів у режимі розробки
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns += [
    path('accounts/', include('django.contrib.auth.urls')),
]
