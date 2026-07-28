// Superseded regression artifact; retained to reproduce known defects.
const printButton = document.querySelector("[data-print]");

printButton?.addEventListener("click", () => {
  window.print();
});
