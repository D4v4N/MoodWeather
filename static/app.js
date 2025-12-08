const form = document.getElementById("location-form");
const locationInput = document.getElementById("location-input");
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const location = locationInput.value.trim();

  if (!location) {
    setStatus("Please enter a city.", true);
    return;
  }

  try {
    setStatus("Fetching weather and playlist…");
    toggleLoading(true);

    // Later on we replace this bullshit with flask backend
    // const response = await fetch(`/api/recommend?location=${encodeURIComponent(location)}`);
    // const data = await response.json();
    const data = await mockRecommendForLocation(location);

    renderResult(data);
    setStatus("");
  } catch (err) {
    console.error(err);
    setStatus("Something went wrong. Try again later.", true);
  } finally {
    toggleLoading(false);
  }
});

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function toggleLoading(isLoading) {
  const button = form.querySelector("button");
  if (isLoading) {
    button.disabled = true;
    button.textContent = "Loading…";
  } else {
    button.disabled = false;
    button.textContent = "Get Mood";
  }
}

function renderResult(data) {
  if (!data) return;

  const { location, weather, mood, playlist } = data;

  resultLocation.textContent = location || "Unknown location";
  resultMood.textContent = mood.label;
  resultMood.title = mood.key;

  weatherDescription.textContent = weather.description;
  weatherTemp.textContent = `${Math.round(weather.temperature)}°C`;

  playlistName.textContent = playlist.name;
  playlistDescription.textContent = playlist.description || "";
  playlistLink.href = playlist.url || "#";

  playlistTracks.innerHTML = "";
  if (Array.isArray(playlist.tracks)) {
    playlist.tracks.forEach((track) => {
      const li = document.createElement("li");
      li.className = "track-item";

      const titleSpan = document.createElement("span");
      titleSpan.className = "track-title";
      titleSpan.textContent = track.title;

      const artistSpan = document.createElement("span");
      artistSpan.className = "track-artist";
      artistSpan.textContent = track.artist;

      li.appendChild(titleSpan);
      li.appendChild(artistSpan);
      playlistTracks.appendChild(li);
    });
  }

  resultSection.classList.remove("hidden");
}

/* some funcky functions */
async function mockRecommendForLocation(location) {
  await new Promise((r) => setTimeout(r, 600));

  const lowered = location.toLowerCase();
  let weatherType = "sunny";

  if (lowered.includes("stockholm") || lowered.includes("göteborg")) {
    weatherType = "cloudy";
  }
  if (lowered.includes("london") || lowered.includes("bergen")) {
    weatherType = "rainy";
  }
  if (lowered.includes("dubai") || lowered.includes("cairo")) {
    weatherType = "hot";
  }

  const weatherByType = {
    sunny: { description: "Sunny", temperature: 22 },
    cloudy: { description: "Cloudy", temperature: 16 },
    rainy: { description: "Rainy", temperature: 12 },
    hot: { description: "Hot", temperature: 32 },
  };

  /* some dummy results for now! but we gonna change the shit*/
  const moodByType = {
    sunny: { key: "energetic", label: "Energetic" },
    cloudy: { key: "chill", label: "Chill" },
    rainy: { key: "cozy", label: "Cozy Rain Vibes" },
    hot: { key: "party", label: "Party" },
  };

  const playlistByType = {
    sunny: {
      name: "Sunny Day Vibes",
      description: "Bright pop & house for sunny days.",
      url: "https://open.spotify.com/search/sunny%20day",
      tracks: [
        { title: "Good Life", artist: "OneRepublic" },
        { title: "Walking On Sunshine", artist: "Katrina & The Waves" },
      ],
    },
    cloudy: {
      name: "Cloudy Chill",
      description: "Soft background beats for grey skies.",
      url: "https://open.spotify.com/search/cloudy%20day%20chill",
      tracks: [
        { title: "Holocene", artist: "Bon Iver" },
        { title: "Yellow", artist: "Coldplay" },
      ],
    },
    rainy: {
      name: "Cozy Rain Vibes (Lo-Fi)",
      description: "Lo-fi and acoustic tracks for rainy evenings.",
      url: "https://open.spotify.com/search/rainy%20day%20lofi",
      tracks: [
        { title: "Snowman", artist: "Wys" },
        { title: "Dreams", artist: "Joakim Karud" },
      ],
    },
    hot: {
      name: "Heatwave Party",
      description: "High-energy tracks for warm nights.",
      url: "https://open.spotify.com/search/summer%20party",
      tracks: [
        { title: "Despacito", artist: "Luis Fonsi" },
        { title: "Lean On", artist: "Major Lazer" },
      ],
    },
  };

  const wt = weatherByType[weatherType] || weatherByType.sunny;
  const mood = moodByType[weatherType] || moodByType.sunny;
  const playlist = playlistByType[weatherType] || playlistByType.sunny;

  return { location, weather: wt, mood, playlist };
}