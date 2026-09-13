const cards = document.querySelectorAll(".member-card");

const popup = document.getElementById("profile-popup");
const closeButton = document.getElementById("close-popup");

const popupName = document.getElementById("popup-name");
const popupRole = document.getElementById("popup-role");
const popupDescription = document.getElementById("popup-description");

const detailRole = document.getElementById("detail-role");
const detailFocus = document.getElementById("detail-focus");
const detailJoined = document.getElementById("detail-joined");
const detailEducation = document.getElementById("detail-education");
const detailAbout = document.getElementById("detail-about");

const popupPhoto = document.getElementById("popup-photo");
const popupParent = popup.parentElement;
const popupNextSibling = popup.nextElementSibling;

let activeCard = null;
let suppressHover = false;


function closeProfile() {

    popup.classList.add("hidden");

    if (activeCard) {
        activeCard.classList.remove("selected");
        activeCard.classList.remove("zoomed");
    }

    if (popup.parentElement !== popupParent) {
        popupParent.insertBefore(popup, popupNextSibling);
    }

    activeCard = null;
}


function openProfile(card) {

    cards.forEach(c => c.classList.remove("selected"));

    card.classList.add("selected");
    activeCard = card;


    popupName.textContent =
        card.dataset.name;

    popupRole.textContent =
        card.dataset.role;

    popupDescription.textContent =
        card.dataset.description;

    detailRole.textContent =
        card.dataset.role;

    detailFocus.textContent =
        card.dataset.focus;

    detailJoined.textContent =
        card.dataset.joined;

    detailEducation.textContent =
        card.dataset.education;

    detailAbout.textContent =
        card.dataset.about;


    const portrait =
        card.querySelector(".portrait");

    popupPhoto.className =
        "popup-photo " +
        [...portrait.classList]
            .filter(name =>
                name.startsWith("portrait-")
            )
            .join(" ");

    popupPhoto.textContent =
        portrait.textContent;


    card.appendChild(popup);
    card.classList.add("zoomed");
    popup.classList.remove("hidden");

    const cardRect = card.getBoundingClientRect();
    const viewportMargin = 20;
    const popupLeft = Math.max(
        viewportMargin,
        Math.min(
            cardRect.left,
            window.innerWidth - viewportMargin - popup.offsetWidth
        )
    );

    popup.style.left = `${popupLeft - cardRect.left}px`;
}


cards.forEach(card => {

    card.addEventListener(
        "mouseenter",
        () => {
            if (!suppressHover) {
                openProfile(card);
            }
        }
    );

    card.addEventListener(
        "click",
        () => openProfile(card)
    );

    card.addEventListener(
        "mouseleave",
        event => {
            if (!popup.contains(event.relatedTarget)) {
                closeProfile();
            }
        }
    );

});


closeButton.addEventListener(
    "click",
    event => {
        event.stopPropagation();
        suppressHover = true;
        closeProfile();
    }
);


popup.addEventListener(
    "mouseleave",
    event => {
        if (!activeCard || !activeCard.contains(event.relatedTarget)) {
            closeProfile();
        }
    }
);


document.addEventListener(
    "mousemove",
    event => {
        if (
            !event.target.closest(".member-card") &&
            !popup.contains(event.target)
        ) {
            suppressHover = false;
        }
    }
);


document.addEventListener(
    "keydown",
    event => {
        if (event.key === "Escape" && activeCard) {
            suppressHover = true;
            closeProfile();
        }
    }
);