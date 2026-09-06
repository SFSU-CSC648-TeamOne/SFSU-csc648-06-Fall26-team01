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


function openProfile(card) {

    cards.forEach(c => c.classList.remove("selected"));

    card.classList.add("selected");


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


    popup.classList.remove("hidden");
}


cards.forEach(card => {

    card.addEventListener(
        "mouseenter",
        () => openProfile(card)
    );

    card.addEventListener(
        "click",
        () => openProfile(card)
    );

});


closeButton.addEventListener(
    "click",
    () => {

        popup.classList.add("hidden");

        cards.forEach(
            card =>
                card.classList.remove("selected")
        );

    }
);