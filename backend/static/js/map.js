// Show basic map
const map = L.map("map").setView([41.0, -72], 5);
const layer = L.tileLayer(
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  {
    maxZoom: 19,
  }
);
layer.addTo(map);

// toggle zoom/pan versus selection mode:
const toggleButton = document.getElementById("toggle-button");
if (toggleButton) {
  toggleButton.addEventListener("click", function () {
    if (map.dragging.enabled()) {
      map.dragging.disable();
      map.scrollWheelZoom.disable();
      toggleButton.innerHTML = "Toggle Zoom/Pan Mode ON";
    } else {
      map.dragging.enable();
      map.scrollWheelZoom.enable();
      toggleButton.innerHTML = "Toggle Select Mode ON";
    }
  });
}

// to represent the bounding box
const currentBbox = {
  start_lat: 0,
  start_lon: 0,
  end_lat: 0,
  end_lon: 0,
};
const boxes = new Array();
let draggingTheMouse = false;

// clear poly
function clearPolygon() {
  map.eachLayer(function (layer) {
    if (layer instanceof L.Polygon) {
      map.removeLayer(layer);
    }
  });
}

// handle mouse events to draw a bounding box
map.on("mousedown", function (e) {
  if (map.dragging.enabled()) {
    return;
  }
  draggingTheMouse = true;
  currentBbox.start_lat = e.latlng.lat;
  currentBbox.start_lon = e.latlng.lng;
});

map.on("mousemove", function (e) {
  if (map.dragging.enabled()) {
    return;
  }
  // Fix so we can start at null island if we want
  if (currentBbox.start_lat === 0 && currentBbox.start_lon === 0) {
    return;
  }
  if (!draggingTheMouse) {
    return;
  }

  clearPolygon();

  // ok we're dragging the mouse and we have a start point, draw the
  // rectangle that's being dragged
  const currentPolygon = L.polygon([
    [currentBbox.start_lat, currentBbox.start_lon],
    [currentBbox.start_lat, e.latlng.lng],
    [e.latlng.lat, e.latlng.lng],
    [e.latlng.lat, currentBbox.start_lon],
  ]);
  currentPolygon.addTo(map);
});

map.on("mouseup", function (e) {
  if (map.dragging.enabled()) {
    return;
  }
  draggingTheMouse = false;
  currentBbox.end_lat = e.latlng.lat;
  currentBbox.end_lon = e.latlng.lng;

  // show the modal
  const modal = document.getElementById("default-modal");
  if (modal) {
    const modalInstance = new window.Flowbite.default.Modal(modal);
    modalInstance.show();
    // add a handler to clear box on hide:
    modalInstance.updateOnHide(() => {
      try {
        clearPolygon();
      } catch (e) {
        console.error(e);
      }
    });
    const submit_button = document.getElementById("submit_bbox");
    if (submit_button) {
      submit_button.onclick = function () {
        modalInstance.hide();
      };
    }
  }

  // get leftmost lon and topmost lat
  const top_left_lon = Math.min(currentBbox.start_lon, currentBbox.end_lon);
  const top_left_lat = Math.max(currentBbox.start_lat, currentBbox.end_lat);
  // get rightmost lon and bottommost lat
  const bottom_right_lon = Math.max(currentBbox.start_lon, currentBbox.end_lon);
  const bottom_right_lat = Math.min(currentBbox.start_lat, currentBbox.end_lat);

  document.getElementById("tl_lat").value = top_left_lat;
  document.getElementById("tl_lon").value = top_left_lon;
  document.getElementById("br_lat").value = bottom_right_lat;
  document.getElementById("br_lon").value = bottom_right_lon;

  // update button state
  document.getElementById("submit_bbox").disabled = false;

  // remove previous polygon - for now, eventually probably want to keep
  // them around
  boxes.forEach((box) => {
    map.removeLayer(box);
  });

  // draw polygon based on mousedown and mouseup events
  const currentPolygon = L.polygon([
    [currentBbox.start_lat, currentBbox.start_lon],
    [currentBbox.start_lat, currentBbox.end_lon],
    [currentBbox.end_lat, currentBbox.end_lon],
    [currentBbox.end_lat, currentBbox.start_lon],
  ]);
  currentPolygon.addTo(map);
  boxes.push(currentPolygon);
});
