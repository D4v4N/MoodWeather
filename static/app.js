const form = document.getElementById("location-form");
const input = document.getElementById("location-input");
const statusMessage = document.getElementById("status-message");
const resultSection = document.getElementById("result-section");

const resultLocation = document.getElementById("result-location");
const resultMood = document.getElementById("result-mood");
const weatherDescription = document.getElementById("weather-description");
const weatherTemp = document.getElementById("weather-temp");

const playlistName = document.getElementById("playlist-name");
const playlistDescription = document.getElementById("playlist-description");
const playlistLink = document.getElementById("playlist-link");
const playlistCover = document.querySelector(".playlist-cover");

// --- Event handler ---
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const city = input.value.trim();
  if (!city) {
    setStatus("Please enter a city.", true);
    return;
  }

  setStatus("Fetching weather...");
  resultSection.classList.add("hidden");

  try {
    const response = await fetch(`/api/recommend?location=${encodeURIComponent(city)}`);
    const data = await response.json();

    if (data.error) {
        throw new Error(data.error);
    }

    // Update UI: Weather
    resultLocation.textContent = data.location;
    weatherDescription.textContent = data.weather.description;
    weatherTemp.textContent = `${Math.round(data.weather.temperature)} °C`;
    resultMood.textContent = data.weather.mood_key.toUpperCase();

    // Update UI: Audius
    playlistName.textContent = data.playlist.name;
    const desc = data.playlist.description || "No description available";
    playlistDescription.textContent = desc.length > 100 ? desc.substring(0, 97) + "..." : desc;

    playlistLink.href = data.playlist.url;
    playlistLink.textContent = "Listen on Audius";

    if (data.playlist.artwork) {
        playlistCover.style.backgroundImage = `url(${data.playlist.artwork})`;
    }

    const playBtn = document.querySelector(".play-btn");
    const playlistBody = document.querySelector(".playlist-body"); // Hela behållaren

    const newPlayBtn = playBtn.cloneNode(true);
    playBtn.parentNode.replaceChild(newPlayBtn, playBtn);

    newPlayBtn.addEventListener("click", () => {
        console.log("Play clicked!");

        let url = data.playlist.url;
        if (url.endsWith("/")) url = url.slice(0, -1);
        const parts = url.split("/");
        const playlistId = parts[parts.length - 1];

        if (playlistId) {
            // döljer den gamla headern
            const header = document.querySelector(".playlist-header");
            if (header) header.style.display = "none";

            // skapar spelaren
            const iframe = document.createElement("iframe");

            iframe.src = `https://audius.co/embed/playlist/${playlistId}?flavor=card`;

            iframe.style.width = "100%";
            iframe.style.height = "500px";
            iframe.style.border = "none";
            iframe.style.borderRadius = "12px";
            iframe.allow = "autoplay; encrypted-media; clipboard-write";

            //rensar hela playlistbodyn
            playlistBody.innerHTML = "";

            // lägger in spelaren
            playlistBody.appendChild(iframe);
        } else {
            console.error("Kunde inte hitta Playlist ID i URL:", data.playlist.url);
        }
    });

    setStatus("");
    resultSection.classList.remove("hidden");

  } catch (err) {
    console.error(err);
    setStatus("Could not fetch weather data.", true);
  }
});

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}
