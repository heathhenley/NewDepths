htmx.on("deletedOrders", function (evt) {
  const orderIds = evt.detail.value;
  orderIds.forEach((orderId) => {
    const orderRow = document.getElementById("order-row-" + orderId);
    if (orderRow) {
      orderRow.remove();
    }
  });
});

htmx.on("showAlert", function (evt) {
  const alert = document.getElementById("toast-simple");
  if (!alert) {
    return;
  }
  const alertText = document.getElementById("toast-message");
  if (!alertText) {
    return;
  }
  alertText.innerText = evt.detail.value;
  alert.classList.remove("hidden");
  setInterval(() => {
    alert.classList.add("hidden");
  }, 4000);
});
