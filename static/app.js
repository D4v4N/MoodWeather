document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
});

function pickLucideIcon(description, mood) {
  const d = (description || "").toLowerCase();

  if (d.includes("thunder") || d.includes("storm")) return "cloud-lightning";
  if (d.includes("snow")) return "snowflake";
  if (d.includes("rain") || d.includes("drizzle")) return "cloud-rain";
  if (d.includes("fog") || d.includes("mist") || d.includes("haze")) return "cloud-fog";
  if (d.includes("cloud")) return "cloud";
  if (d.includes("clear")) return "sun";

  if (mood === "happy") return "sun";
  if (mood === "sad") return "cloud-rain";
  return "cloud";
}

function setWeatherIcons(iconName) {
  const small = document.getElementById("weather-icon");
  const big = document.getElementById("weather-icon-big");

  if (small) small.setAttribute("data-lucide", iconName);
  if (big) big.setAttribute("data-lucide", iconName);

  if (window.lucide) lucide.createIcons();
}

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

let recommendationId = null;

let currentAbortController = null;

let playerState = {
  tracks: [],
  index: 0,
  audio: null,
};

function stopEmbeddedPlayback() {
  // Backwards-compatible name (we no longer embed iframes)
  const audio = playerState.audio;
  if (audio) {
    try {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    } catch (_) {}
  }

  playerState.tracks = [];
  playerState.index = 0;
  playerState.audio = null;

  const playlistBody = document.querySelector(".playlist-body");
  if (playlistBody) playlistBody.innerHTML = "";
}

function getAudiusPlaylistId(playlist) {
  if (!playlist) return "";

  const explicitId = playlist.id || playlist.playlist_id || playlist.playlistId;
  if (explicitId) return String(explicitId);

  const rawUrl = playlist.url ? String(playlist.url) : "";
  if (!rawUrl) return "";

  let url = rawUrl;
  if (url.endsWith("/")) url = url.slice(0, -1);
  const parts = url.split("/");
  return parts[parts.length - 1] || "";
}

function renderNativePlayer(tracks) {
  const playlistBody = document.querySelector(".playlist-body");
  if (!playlistBody) return;

  stopEmbeddedPlayback();

  if (!Array.isArray(tracks) || tracks.length === 0) {
    playlistBody.innerHTML = "<p style='opacity:.85'>No tracks available for this playlist.</p>";
    return;
  }

  // Player shell
  playlistBody.innerHTML = `
    <div class="native-player" style="display:flex;flex-direction:column;gap:12px;">
      <div class="native-player__now" style="display:flex;align-items:center;gap:12px;">
        <div class="native-player__art" style="width:56px;height:56px;border-radius:12px;background-size:cover;background-position:center;flex:0 0 auto;"></div>
        <div style="min-width:0;">
          <div class="native-player__title" style="font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div>
          <div class="native-player__artist" style="opacity:.85;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></div>
        </div>
      </div>

      <audio class="native-player__audio" preload="none" controls style="width:100%;"></audio>

      <div class="native-player__controls" style="display:flex;gap:10px;">
        <button type="button" class="native-player__prev" style="padding:8px 12px;border-radius:10px;">Prev</button>
        <button type="button" class="native-player__next" style="padding:8px 12px;border-radius:10px;">Next</button>
      </div>

      <div class="native-player__list" style="max-height:260px;overflow:auto;border-radius:12px;">
        ${tracks
          .map(
            (t, i) => `
              <button type="button" class="native-player__item" data-index="${i}" style="width:100%;text-align:left;padding:10px 12px;background:transparent;border:0;cursor:pointer;">
                <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(t.title || "Unknown track")}</div>
                <div style="opacity:.85;font-size:.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(t.artist || "Unknown artist")}</div>
              </button>
            `
          )
          .join("")}
      </div>
    </div>
  `;

  const audio = playlistBody.querySelector(".native-player__audio");
  const art = playlistBody.querySelector(".native-player__art");
  const title = playlistBody.querySelector(".native-player__title");
  const artist = playlistBody.querySelector(".native-player__artist");
  const prevBtn = playlistBody.querySelector(".native-player__prev");
  const nextBtn = playlistBody.querySelector(".native-player__next");
  const list = playlistBody.querySelector(".native-player__list");

  playerState.tracks = tracks;
  playerState.index = 0;
  playerState.audio = audio;

  function setActive(index, autoplay = true) {
    const t = playerState.tracks[index];
    if (!t || !t.stream_url) return;

    playerState.index = index;

    if (title) title.textContent = t.title || "Unknown track";
    if (artist) artist.textContent = t.artist || "Unknown artist";
    if (art) art.style.backgroundImage = t.artwork ? `url(${t.artwork})` : "";

    // highlight
    if (list) {
      list.querySelectorAll(".native-player__item").forEach((btn) => {
        btn.style.opacity = "0.9";
        btn.style.background = "transparent";
      });
      const activeBtn = list.querySelector(`.native-player__item[data-index='${index}']`);
      if (activeBtn) {
        activeBtn.style.opacity = "1";
        activeBtn.style.background = "rgba(255,255,255,0.06)";
      }
    }

    try {
      audio.pause();
      audio.src = t.stream_url;
      audio.load();
      if (autoplay) audio.play().catch(() => {});
    } catch (_) {}
  }

  // Wire controls
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      const nextIndex = (playerState.index - 1 + playerState.tracks.length) % playerState.tracks.length;
      setActive(nextIndex);
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      const nextIndex = (playerState.index + 1) % playerState.tracks.length;
      setActive(nextIndex);
    });
  }

  if (list) {
    list.addEventListener("click", (e) => {
      const btn = e.target.closest(".native-player__item");
      if (!btn) return;
      const idx = Number(btn.dataset.index);
      if (Number.isFinite(idx)) setActive(idx);
    });
  }

  audio.addEventListener("ended", () => {
    const nextIndex = (playerState.index + 1) % playerState.tracks.length;
    setActive(nextIndex);
  });

  // Start with first track (but don't force autoplay if browser blocks it)
  setActive(0, true);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadPlaylistTracks(playlist) {
  const playlistId = getAudiusPlaylistId(playlist);
  if (!playlistId) {
    console.warn("No playlist id available.", playlist);
    return;
  }

  const playlistBody = document.querySelector(".playlist-body");
  if (playlistBody) {
    playlistBody.innerHTML = "<p style='opacity:.85'>Loading tracks…</p>";
  }

  const res = await fetch(`/api/music/playlist/${encodeURIComponent(playlistId)}/tracks?limit=25`, {
    cache: "no-store",
  });

  let data = null;
  try {
    data = await res.json();
  } catch (_) {}

  if (!res.ok) {
    const msg = (data && (data.detail || data.error)) ? (data.detail || data.error) : `Tracks request failed (${res.status})`;
    throw new Error(msg);
  }

  const tracks = (data && data.tracks) ? data.tracks : [];
  renderNativePlayer(tracks);
}

function resetResultsUI() {
  // Clear status and hide results until we have fresh data
  setStatus("");

  // Stop audio + remove the embedded player
  stopEmbeddedPlayback();

  // Clear previous results (defensive: elements might not exist)
  if (resultLocation) resultLocation.textContent = "";
  if (resultMood) resultMood.textContent = "—";
  if (weatherDescription) weatherDescription.textContent = "";
  if (weatherTemp) weatherTemp.textContent = "";

  if (playlistName) playlistName.textContent = "";
  if (playlistDescription) playlistDescription.textContent = "";

  if (playlistLink) {
    playlistLink.removeAttribute("href");
    playlistLink.textContent = "";
  }

  if (playlistCover) {
    playlistCover.style.backgroundImage = "";
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const city = input.value.trim();
  if (!city) {
    setStatus("Please enter a city.", true);
    return;
  }

  // Cancel any in-flight request (rapid re-search / double click)
  if (currentAbortController) {
    currentAbortController.abort();
  }
  currentAbortController = new AbortController();

  // Reset UI so the previous playlist doesn't linger
  resetResultsUI();

  setStatus("Fetching weather...");
  resultSection.classList.add("hidden");

  try {
    const response = await fetch(
      `/api/recommend?location=${encodeURIComponent(city)}`,
      { cache: "no-store", signal: currentAbortController.signal }
    );

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      // ignore JSON parse errors; handled below via status code
    }

    if (!response.ok) {
      const msg = (data && (data.detail || data.error))
        ? (data.detail || data.error)
        : `Request failed (${response.status})`;
      throw new Error(msg);
    }

    if (!data || !data.weather || !data.playlist) {
      throw new Error("Unexpected API response");
    }

    recommendationId = data.recommendation_id || data.recommendationId || null;

    if (data.error) throw new Error(data.error);

    if (resultLocation) resultLocation.textContent = data.location;
    if (weatherDescription) weatherDescription.textContent = data.weather.description;
    if (weatherTemp) weatherTemp.textContent = `${Math.round(data.weather.temperature)} °C`;

    const moodKey = (data.weather.mood_key || data.weather.mood || "").toString();
    if (resultMood) resultMood.textContent = moodKey ? moodKey.toUpperCase() : "—";

    if (playlistName) playlistName.textContent = data.playlist.name;

    const desc = data.playlist.description || "No description available";
    if (playlistDescription) playlistDescription.textContent = desc.length > 100 ? desc.substring(0, 97) + "..." : desc;

    if (playlistLink) {
      playlistLink.href = data.playlist.url;
      playlistLink.textContent = "Listen on Audius";
    }

    if (playlistCover && data.playlist.artwork) {
      playlistCover.style.backgroundImage = `url(${data.playlist.artwork})`;
    }

    // Dynamisk väder-ikon
    const icon = pickLucideIcon(data.weather.description, data.weather.mood_key);
    setWeatherIcons(icon);

    await loadPlaylistTracks(data.playlist);

    setStatus("");
    resultSection.classList.remove("hidden");
  } catch (err) {
    if (err && err.name === "AbortError") return;
    console.error(err);
    setStatus(err?.message || "Could not fetch weather data.", true);
  }
});

//regenerate new playlist-knappen i playerbar
const shuffleBtn = document.getElementById("shuffle-btn");

if (shuffleBtn) {
 shuffleBtn.addEventListener("click", async () => {
  if (!recommendationId) {
   setStatus("Fetch recommendation first.", true);
   return;
   }

 try {
  setStatus("Randomizing new playlist...")

  stopEmbeddedPlayback();

  const res = await fetch(
    `/api/recommend/regenerate?recommendation_id=${encodeURIComponent(recommendationId)}`,
    { cache: "no-store" }
  );

  let data = null;
  try { data = await res.json(); } catch (_) {}

  if (!res.ok) {
    throw new Error((data && (data.detail || data.error)) || "Couldn't generate new playlist");
  }

  if (!data || !data.playlist) {
    throw new Error("Unexpected API response");
  }

  //uppdatera endast playlistdelen
  playlistName.textContent = data.playlist.name;

  const desc = data.playlist.description || "No description available";
  playlistDescription.textContent =
    desc.length > 100 ? desc.substring(0, 97) + "..." : desc;

  playlistLink.href = data.playlist.url;

   if (data.playlist.artwork) {
    playlistCover.style.backgroundImage = `url(${data.playlist.artwork})`;
   }

   await loadPlaylistTracks(data.playlist);

    setStatus("");
  } catch (err) {
    console.error(err);
    setStatus(err?.message || "Couldn't randomize new playlist", true);
   }
  });
 }


function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}
