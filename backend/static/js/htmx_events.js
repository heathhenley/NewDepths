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
  // TODO add cooler alerts that change based on the type of alert
  const alert = document.getElementById("toast-simple");
  const newAlert = alert.parentNode.appendChild(alert.cloneNode(true));
  if (!alert || !newAlert || !evt.detail.value) {
    return;
  }
  // change id so we don't grab the same alert again
  newAlert.id = "toast-" + Math.random().toString(32).substring(4);
  const alertText = newAlert.querySelector("#toast-message");
  if (!alertText) {
    return;
  }
  alertText.innerText = evt.detail.value;
  newAlert.classList.remove("hidden");
  setInterval(() => {
    newAlert.remove();
  }, 4000);
});
