htmx.on("deletedOrders", function (evt) {
  const orderIds = evt.detail.value;
  orderIds.forEach((orderId) => {
    const orderRow = document.getElementById("order-row-" + orderId);
    if (orderRow) {
      orderRow.remove();
    }
  });
});
