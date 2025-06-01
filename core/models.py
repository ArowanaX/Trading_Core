from django.db import models


class BaseModel(models.Model):
    # Abstract model for created_at and updated_at  and filled at fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    filled_at = models.DateTimeField(null=True,blank=True)

    class Meta:
        abstract = True