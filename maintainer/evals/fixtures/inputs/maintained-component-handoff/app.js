const banners = [...document.querySelectorAll(".service-banner")];

const copy = {
  ok: ["Account tools are available", "You can continue managing this sample account."],
  warning: ["Some requests are delayed", "Try again in a few minutes."],
  critical: ["Account tools are unavailable", "Wait and try again later."],
};

function setLevel(level) {
  for (const banner of banners) {
    banner.dataset.level = level;
    banner.hidden = false;
    banner.querySelector("strong").textContent = copy[level][0];
    banner.querySelector("p").textContent = copy[level][1];
  }
}

for (const control of document.querySelectorAll("[data-level-control]")) {
  control.addEventListener("click", () => setLevel(control.dataset.levelControl));
}

for (const button of document.querySelectorAll("[data-dismiss]")) {
  button.addEventListener("click", () => {
    button.closest(".service-banner").hidden = true;
    document.dispatchEvent(new CustomEvent("service-banner:dismiss"));
  });
}
