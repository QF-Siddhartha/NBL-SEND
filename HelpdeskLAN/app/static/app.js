// Small helpers. No external libraries.
document.addEventListener("submit", function (e) {
  var msg = e.target.getAttribute("data-confirm");
  if (msg && !window.confirm(msg)) e.preventDefault();
});

// Admin filter dropdowns submit their form immediately.
document.querySelectorAll("select[data-autosubmit]").forEach(function (el) {
  el.addEventListener("change", function () { el.form.submit(); });
});

// Warn before submitting a file that is too large (server checks too).
document.querySelectorAll("input[type=file][data-max-bytes]").forEach(function (input) {
  input.addEventListener("change", function () {
    var max = parseInt(input.getAttribute("data-max-bytes"), 10);
    var f = input.files && input.files[0];
    if (f && f.size > max) {
      alert("This file is larger than 5 MB. Please choose a smaller file or a screenshot.");
      input.value = "";
    }
  });
});
