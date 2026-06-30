// Mobile nav toggle
const navToggle = document.getElementById("navToggle");
const headerContact = document.getElementById("headerContact");
if (navToggle) {
  navToggle.addEventListener("click", () => headerContact.classList.toggle("open"));
}

// Hero slideshow auto-rotate
(function () {
  const slideshow = document.getElementById("heroSlideshow");
  if (!slideshow) return;
  const slides = slideshow.querySelectorAll(".hero-slide");
  if (slides.length < 2) return;
  let idx = 0;
  setInterval(() => {
    slides[idx].classList.remove("active");
    idx = (idx + 1) % slides.length;
    slides[idx].classList.add("active");
  }, 4000);
})();

// Enquiry modal
function openEnquiryModal(serviceName) {
  const modal = document.getElementById("enquiryModal");
  const field = document.getElementById("enquiryServiceName");
  if (field) field.value = serviceName || "";
  modal.classList.add("open");
}
function closeEnquiryModal() {
  document.getElementById("enquiryModal").classList.remove("open");
  document.getElementById("enquiryStatus").textContent = "";
  document.getElementById("enquiryStatus").className = "form-status";
}
document.getElementById("enquiryModal")?.addEventListener("click", (e) => {
  if (e.target.id === "enquiryModal") closeEnquiryModal();
});

const enquiryForm = document.getElementById("enquiryForm");
if (enquiryForm) {
  enquiryForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("enquiryStatus");
    const formData = new FormData(enquiryForm);
    status.textContent = "Sending...";
    status.className = "form-status";
    try {
      const res = await fetch("/enquiry", { method: "POST", body: formData });
      const data = await res.json();
      if (data.ok) {
        status.textContent = "Thank you! We'll contact you shortly.";
        status.className = "form-status success";
        enquiryForm.reset();
        setTimeout(closeEnquiryModal, 1800);
      } else {
        status.textContent = data.error || "Something went wrong.";
        status.className = "form-status error";
      }
    } catch {
      status.textContent = "Network error. Please try again.";
      status.className = "form-status error";
    }
  });
}
