function showModalOnLoad(modalId) {
  window.onload = () => {
    const modalEl = document.getElementById(modalId);
    if (!modalEl) {
      return;
    }
    const modal = new window.Flowbite.default.Modal(modalEl);
    modal.show();
  }
}