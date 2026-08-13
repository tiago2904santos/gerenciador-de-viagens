from django import forms


class MainPreviewFiltersForm(forms.Form):
    """Campos reais usados apenas pela rota DEBUG da página-piloto."""

    sort = forms.ChoiceField(
        label="Ordenação",
        choices=(
            ("number_desc", "Número: maior"),
            ("number_asc", "Número: menor"),
        ),
        widget=forms.Select(attrs={"aria-label": "Ordenação"}),
    )
    status = forms.ChoiceField(
        label="Status",
        choices=(
            ("all", "Todos os status"),
            ("finished", "Finalizados"),
        ),
        widget=forms.Select(attrs={"aria-label": "Status"}),
    )
