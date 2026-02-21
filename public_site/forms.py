from django import forms


class ContactForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    pet_type = forms.ChoiceField(
        choices=[
            ("dog", "Dog"),
            ("cat", "Cat"),
            ("other", "Other"),
        ]
    )
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
