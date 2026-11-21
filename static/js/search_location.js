// Optional: lets a visitor sort by distance. The search page works without this file.
(function () {
  var button = document.getElementById("use-location");
  var latitude = document.getElementById("search-latitude");
  var longitude = document.getElementById("search-longitude");
  if (!button || !latitude || !longitude || !navigator.geolocation) {
    return;
  }
  button.hidden = false;
  button.addEventListener("click", function () {
    navigator.geolocation.getCurrentPosition(function (position) {
      latitude.value = position.coords.latitude;
      longitude.value = position.coords.longitude;
      latitude.disabled = false;
      longitude.disabled = false;
      button.form.submit();
    });
  });
})();
