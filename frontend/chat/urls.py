from django.urls import path, re_path

from chat import views

# Só ids hexadecimais de 32 caracteres chegam ao backend.
ID = r'(?P<projeto_id>[0-9a-f]{32})'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/saude', views.saude, name='saude'),
    path('api/projetos', views.projetos, name='projetos'),
    re_path(rf'^api/projetos/{ID}$', views.projeto, name='projeto'),
    re_path(rf'^api/projetos/{ID}/chat$', views.chat, name='chat'),
]
