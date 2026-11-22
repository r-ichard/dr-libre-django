// Every field component marks an invalid control with aria-invalid, so one selector serves all forms.
const firstInvalid = document.querySelector('[data-autofocus], [aria-invalid="true"]');
if (firstInvalid) {
  firstInvalid.focus();
}
