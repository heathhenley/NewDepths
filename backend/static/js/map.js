// Show basic map
const map = L.map("map").setView([51.505, -0.09], 13);
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

// handle mouse events to draw a bounding box
map.on("mousedown", function (e) {
  if (map.dragging.enabled()) {
    return;
  }
  currentBbox.start_lat = e.latlng.lat;
  currentBbox.start_lon = e.latlng.lng;
});

map.on("mouseup", function (e) {
  if (map.dragging.enabled()) {
    return;
  }

  currentBbox.end_lat = e.latlng.lat;
  currentBbox.end_lon = e.latlng.lng;


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
  ])
  currentPolygon.addTo(map);
  boxes.push(currentPolygon);
});