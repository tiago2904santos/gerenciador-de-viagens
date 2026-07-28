"""Canonical CSS contracts for Django form widgets.

Form declarations choose a semantic style from :class:`WidgetStyle`; the
corresponding CSS class string is defined only in this module.
"""

from enum import StrEnum

from django.forms.widgets import Widget


class WidgetStyle(StrEnum):
    """Exact, pre-P-04 class values emitted by the project's forms."""

    UNSTYLED = ""
    AUTH_FIELD_INPUT = "auth-field-input"
    FORM_CONTROL = "form-control"
    FORM_SELECT = "form-select"
    FIELD_CONTROL = "cv-field__control"
    SEARCH_PICKER_NATIVE = "cv-search-picker__native"
    FIELD_CONTROL_TEXTAREA = "cv-field__control cv-field__control--textarea"
    FORM_SELECT_SEARCH_PICKER = "form-select cv-search-picker__native"
    FORM_CONTROL_FIELD_CONTROL = "form-control cv-field__control"
    EVENT_DOCUMENT_SOURCE = "evento-doc-source-select"
    CARD_TOGGLE_SR_ONLY = "app-card-toggle__input sr-only"
    CARD_TOGGLE = "app-card-toggle__input"
    FORM_SELECT_FIELD_CONTROL = "form-select cv-field__control cv-field__control--select"
    FORM_SELECT_TERMS_PICKER = "form-select cv-search-picker__termos-native"
    SEARCH_PICKER_INPUT = "cv-search-picker__input"
    TERM_OFICIO_OS_SOURCE = "termo-oficio-source-select os-oficio-source-select"
    PT_PRESET_ACTIVITY_GRID = "pt-preset-activity-grid"
    PRESTACAO_FILE_INPUT = "form-control cv-field__control prestacao-file-input"
    TERM_OFICIO_SOURCE = "termo-oficio-source-select"


def widget_attrs(style: WidgetStyle) -> dict[str, str]:
    """Build the canonical class attribute for a widget declaration."""

    return {"class": style.value}


def set_widget_style(widget: Widget, style: WidgetStyle, *, overwrite: bool = True) -> None:
    """Apply a canonical class to an existing widget.

    ``overwrite=False`` preserves the former ``dict.setdefault`` behavior used
    by forms that style model-generated widgets.
    """

    if overwrite:
        widget.attrs["class"] = style.value
    else:
        widget.attrs.setdefault("class", style.value)
