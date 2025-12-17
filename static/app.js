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
const playlistTracks = document.getElementById("playlist-tracks");
const playlistLink = document.getElementById("playlist-link");

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
    const response = await fetch(`/api/weather/${city}`);

    if (!response.ok) {
      throw new Error("City not found");
    }

    const data = await response.json();

    // Update UI with backend data
    resultLocation.textContent = data.city;
    weatherDescription.textContent = data.description;
    weatherTemp.textContent = `${Math.round(data.temperature)} °C`;
    resultMood.textContent = data.mood.toUpperCase();

    setStatus("");
    resultSection.classList.remove("hidden");

  } catch (err) {
    console.error(err);
    setStatus("Could not fetch weather data.", true);
  }
});

// --- Helper function ---
function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}
