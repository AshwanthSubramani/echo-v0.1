console.log("Script loaded - Starting execution");

let audioPlayer;
let songQueue = [];
let currentSongIndex = -1;
let allSongs = [];
let playlists = [];
let selectedPlaylist = null;
let isShuffling = false;
let originalQueue = [];
let history = {};

function initAudioPlayer() {
    console.log("initAudioPlayer called");
    audioPlayer = document.getElementById('audio-player');
    if (!audioPlayer) {
        console.error("Audio player element not found!");
        return;
    }
    audioPlayer.addEventListener('ended', () => {
        console.log("Audio ended event triggered");
        if (songQueue.length > 0 && currentSongIndex + 1 < songQueue.length) {
            playNext();
        } else {
            stopPlayer();
        }
        updateHistory();
    });
    audioPlayer.addEventListener('error', (e) => {
        console.error("Audio playback error:", e);
        const playerInfo = document.getElementById('current-song-title');
        if (playerInfo) playerInfo.textContent = 'Error playing song, skipping...';
        playNext();
    });
    audioPlayer.addEventListener('loadeddata', () => {
        console.log("Audio loadeddata event, duration:", audioPlayer.duration);
        audioPlayer.play().catch(e => console.error("Play failed:", e));
        updateProgress();
        updatePlayerUI();
    });
    audioPlayer.addEventListener('timeupdate', updateProgress);
    audioPlayer.addEventListener('play', () => {
        const playPause = document.getElementById('play-pause');
        if (playPause) playPause.innerHTML = '<i class="fas fa-pause"></i>';
    });
    audioPlayer.addEventListener('pause', () => {
        const playPause = document.getElementById('play-pause');
        if (playPause) playPause.innerHTML = '<i class="fas fa-play"></i>';
    });
}

function attachControlPanelListeners() {
    console.log("Attaching control panel listeners");
    const previousBtn = document.getElementById('previous-btn');
    const playPauseBtn = document.getElementById('play-pause');
    const nextBtn = document.getElementById('next-btn');
    const shuffleBtn = document.getElementById('shuffle-btn');
    const progress = document.getElementById('progress');
    const volume = document.getElementById('volume');

    if (previousBtn) previousBtn.addEventListener('click', playPrevious);
    if (playPauseBtn) playPauseBtn.addEventListener('click', togglePlayPause);
    if (nextBtn) nextBtn.addEventListener('click', playNext);
    if (shuffleBtn) shuffleBtn.addEventListener('click', toggleShuffle);
    if (progress) progress.addEventListener('input', seek);
    if (volume) volume.addEventListener('input', setVolume);
}

function updateProgress() {
    const progress = document.getElementById('progress');
    const currentTime = document.getElementById('current-time');
    const duration = document.getElementById('duration');
    if (progress && currentTime && duration && audioPlayer.duration) {
        const percent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        progress.value = isNaN(percent) ? 0 : percent;
        currentTime.textContent = formatTime(audioPlayer.currentTime);
        duration.textContent = formatTime(audioPlayer.duration);
    }
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

async function playSong(songId) {
    console.log("playSong called with songId:", songId);
    const song = allSongs.find(s => s.id === parseInt(songId));
    if (!song) {
        console.log("Song not found for songId:", songId);
        alert("Song not found!");
        return;
    }
    console.log("Found song:", song);

    const playlistSongs = allSongs.filter(s => s.playlist === song.playlist).sort((a, b) => a.position - b.position);
    songQueue = playlistSongs;
    originalQueue = [...playlistSongs];
    currentSongIndex = playlistSongs.findIndex(s => s.id === song.id);
    if (isShuffling) {
        songQueue = smartShuffle(playlistSongs, song);
        currentSongIndex = songQueue.findIndex(s => s.id === song.id);
    }
    console.log("Setting audio src to:", song.url);
    audioPlayer.src = song.url;
    try {
        await audioPlayer.load();
        console.log("Audio loaded successfully");
        audioPlayer.play();
    } catch (e) {
        console.error("Failed to load or play audio:", e);
        alert("Failed to play song: " + e.message);
    }
    updatePlayerUI();
    console.log("Playing song:", song, "Queue:", songQueue, "Index:", currentSongIndex);
}

function addToQueue(songId) {
    console.log("addToQueue called with songId:", songId);
    const song = allSongs.find(s => s.id === parseInt(songId));
    if (!song) return;

    if (songQueue.length === 0) {
        songQueue = [song];
        originalQueue = [song];
        currentSongIndex = 0;
        audioPlayer.src = song.url;
        audioPlayer.load();
    } else {
        songQueue.push(song);
        originalQueue.push(song);
    }
    updatePlayerUI();
    console.log("Added to queue:", song, "Queue:", songQueue);
}

function playNext() {
    console.log("playNext called");
    currentSongIndex++;
    if (currentSongIndex < songQueue.length) {
        const nextSong = songQueue[currentSongIndex];
        audioPlayer.src = nextSong.url;
        audioPlayer.load();
        updatePlayerUI();
        console.log("Next song:", nextSong, "Index:", currentSongIndex);
    } else {
        stopPlayer();
        console.log("End of queue reached");
    }
}

function playPrevious() {
    console.log("playPrevious called");
    currentSongIndex--;
    if (currentSongIndex >= 0) {
        const prevSong = songQueue[currentSongIndex];
        audioPlayer.src = prevSong.url;
        audioPlayer.load();
        updatePlayerUI();
        console.log("Previous song:", prevSong, "Index:", currentSongIndex);
    }
}

function stopPlayer() {
    console.log("stopPlayer called");
    audioPlayer.pause();
    audioPlayer.src = '';
    const playerInfo = document.getElementById('current-song-title');
    if (playerInfo) playerInfo.textContent = 'Select a song to play';
    songQueue = [];
    originalQueue = [];
    currentSongIndex = -1;
    updatePlayerUI();
    updateProgress();
    console.log("Player stopped");
}

function clearQueue() {
    console.log("clearQueue called");
    stopPlayer();
    songQueue = [];
    originalQueue = [];
    currentSongIndex = -1;
    updatePlayerUI();
    showQueueView();
}

function togglePlayPause() {
    console.log("togglePlayPause called");
    if (audioPlayer.paused) {
        audioPlayer.play().catch(e => console.error("Play failed:", e));
    } else {
        audioPlayer.pause();
    }
}

function seek(event) {
    const progress = document.getElementById('progress');
    if (progress && audioPlayer.duration) {
        const seekPosition = (event.target.value / 100) * audioPlayer.duration;
        audioPlayer.currentTime = seekPosition;
    }
}

function setVolume() {
    const volume = document.getElementById('volume');
    if (volume) audioPlayer.volume = volume.value / 100;
}

function toggleShuffle() {
    console.log("toggleShuffle called");
    isShuffling = !isShuffling;
    const shuffleBtn = document.getElementById('shuffle-btn');
    if (shuffleBtn) shuffleBtn.classList.toggle('active', isShuffling);
    
    if (isShuffling) {
        if (songQueue.length > 0) {
            const currentSong = songQueue[currentSongIndex];
            songQueue = smartShuffle(originalQueue, currentSong);
            currentSongIndex = songQueue.findIndex(s => s.id === currentSong.id);
        }
    } else {
        if (songQueue.length > 0) {
            const currentSong = songQueue[currentSongIndex];
            songQueue = [...originalQueue];
            currentSongIndex = songQueue.findIndex(s => s.id === currentSong.id);
        }
    }
    updatePlayerUI();
    console.log("Shuffle toggled:", isShuffling, "Queue:", songQueue);
}

function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function smartShuffle(songs, currentSong = null) {
    console.log("smartShuffle called with songs:", songs, "currentSong:", currentSong);
    
    if (songs.length === 0) return [];

    let remainingSongs = songs.filter(song => song !== currentSong);
    const artistGroups = new Map();
    for (let song of remainingSongs) {
        if (!artistGroups.has(song.artist)) {
            artistGroups.set(song.artist, []);
        }
        artistGroups.get(song.artist).push(song);
    }

    let shuffled = [];
    let artistList = Array.from(artistGroups.keys());
    while (artistList.length > 0) {
        const artistIndex = randomInt(0, artistList.length - 1);
        const selectedArtist = artistList[artistIndex];
        const artistSongs = artistGroups.get(selectedArtist);
        const songIndex = randomInt(0, artistSongs.length - 1);
        shuffled.push(artistSongs[songIndex]);
        artistSongs.splice(songIndex, 1);
        if (artistSongs.length === 0) {
            artistList.splice(artistIndex, 1);
        }
    }

    if (currentSong) {
        shuffled.unshift(currentSong);
    }
    return shuffled;
}

function shuffle(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = randomInt(0, i);
        [array[i], array[j]] = [array[j], array[i]];
    }
    return array;
}

function getTopPlaylists(history, count = 2) {
    const playlistCounts = {};
    for (let songId in history) {
        const song = allSongs.find(s => s.id === parseInt(songId));
        if (song && song.playlist) {
            playlistCounts[song.playlist] = (playlistCounts[song.playlist] || 0) + history[songId];
        }
    }
    return Object.entries(playlistCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, count)
        .map(entry => entry[0]);
}

function updateHistory() {
    if (songQueue.length > 0 && currentSongIndex >= 0 && currentSongIndex < songQueue.length) {
        const songId = songQueue[currentSongIndex].id;
        history[songId] = (history[songId] || 0) + 1;
    }
}

function playPlaylist(playlistName) {
    console.log("playPlaylist called with:", playlistName);
    const playlistSongs = allSongs.filter(song => song.playlist === playlistName).sort((a, b) => a.position - b.position);
    songQueue = playlistSongs;
    originalQueue = [...playlistSongs];
    currentSongIndex = -1;
    if (isShuffling) {
        songQueue = smartShuffle(playlistSongs);
        currentSongIndex = 0;
    }
    playNext();
}

function showEditPlaylistPopup(playlistId, playlistName) {
    console.log("showEditPlaylistPopup called with:", playlistId, playlistName);
    if (!playlistId) {
        alert("Cannot edit this playlist. Please create it through the interface.");
        return;
    }
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showPlaylistSongs('${playlistName.replace(/'/g, "\\'")}')"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Edit Playlist: ${playlistName}</h2>
        <div class="edit-playlist-actions">
            <button onclick="updatePlaylistImage(${playlistId})">Change Image</button>
            <button onclick="renamePlaylist(${playlistId}, '${playlistName.replace(/'/g, "\\'")}')">Rename Playlist</button>
            <button onclick="deletePlaylist(${playlistId})">Delete Playlist</button>
        </div>
    `;
    attachControlPanelListeners();
}

function updatePlaylistImage(playlistId) {
    console.log("updatePlaylistImage called with:", playlistId);
    if (!playlistId) {
        alert("Invalid playlist ID. Please try again.");
        return;
    }
    const imageInput = document.createElement('input');
    imageInput.type = 'file';
    imageInput.accept = 'image/*';
    imageInput.onchange = () => {
        if (imageInput.files.length > 0) {
            const formData = new FormData();
            formData.append('playlist_id', playlistId);
            formData.append('image', imageInput.files[0]);
            fetch('/update_playlist_image', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) throw new Error(`Image update failed: ${response.statusText}`);
                return response.json();
            })
            .then(data => {
                alert(data.message);
                fetchPlaylists();
                showMainView();
            })
            .catch(error => {
                console.error("Error updating playlist image:", error);
                alert("Failed to update playlist image: " + error.message);
            });
        }
    };
    imageInput.click();
}

function renamePlaylist(playlistId, currentName) {
    console.log("renamePlaylist called with:", playlistId, currentName);
    if (!playlistId) {
        alert("Invalid playlist ID. Please try again.");
        return;
    }
    const newName = prompt("Enter new playlist name:", currentName);
    if (newName === null) return;

    fetch('/rename_playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `playlist_id=${encodeURIComponent(playlistId)}&new_name=${encodeURIComponent(newName)}`
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.message || 'Rename failed'); });
        }
        return response.json();
    })
    .then(data => {
        alert(data.message);
        fetchPlaylists();
        if (selectedPlaylist === currentName) {
            selectedPlaylist = newName;
            showPlaylistSongs(newName);
        } else {
            showMainView();
        }
    })
    .catch(error => {
        console.error("Error renaming playlist:", error);
        alert(`Failed to rename playlist: ${error.message}`);
    });
}

function showPlaylistSongs(playlistName) {
    console.log("showPlaylistSongs called with:", playlistName);
    selectedPlaylist = playlistName;
    const playlistSongs = allSongs.filter(song => song.playlist === playlistName).sort((a, b) => a.position - b.position);
    const playlist = playlists.find(p => p.name === playlistName);
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showPlaylistsView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Songs in ${playlistName}</h2>
        <div class="edit-playlist-actions">
            <button onclick="showEditPlaylistPopup(${playlist.id}, '${playlistName.replace(/'/g, "\\'")}')">Edit Playlist</button>
        </div>
        <div class="song-list" id="songs-container">
            ${playlistSongs.length === 0 ? '<p>No songs found in this playlist.</p>' : playlistSongs.map(song => `
                <div class="song-item" draggable="true" data-id="${song.id}" data-song-id="${song.id}">
                    <i class="far fa-waveform"></i>
                    <span onclick="playSong(${song.id})" style="cursor: pointer;">${song.title} - ${song.artist}</span>
                    <button onclick="addToQueue(${song.id})"><i class="fas fa-plus"></i></button>
                    <button onclick="deleteSong(${song.id})" class="delete-btn"><i class="fas fa-trash"></i></button>
                </div>
            `).join('')}
        </div>
    `;
    attachControlPanelListeners();
    makeSortable();
}

function createPlaylist() {
    console.log("createPlaylist called");
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showMainView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Create Playlist</h2>
        <form id="create-playlist-form" class="create-playlist-form">
            <input type="text" name="playlist_name" id="playlist-name" placeholder="Playlist Name" required>
            <button type="submit">Create</button>
        </form>
    `;
    attachControlPanelListeners();
}

function handleCreatePlaylist(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    fetch('/create_playlist', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        fetchPlaylists();
        showMainView();
    })
    .catch(error => console.error('Error creating playlist:', error));
}

function addSong() {
    console.log("addSong called");
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showMainView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Add Song</h2>
        <form id="add-song-form" class="add-song-form">
            <select name="playlist_name" id="add-song-playlist" required>
                <option value="">Select Playlist</option>
                ${playlists.map(playlist => `<option value="${playlist.name}">${playlist.name}</option>`).join('')}
            </select>
            <input type="text" name="youtube_url" id="youtube-url" placeholder="YouTube URL" required>
            <button type="submit">Add Song</button>
        </form>
    `;
    attachControlPanelListeners();
}

function handleAddSong(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    fetch('/add_song', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        fetchSongs();
        showMainView();
    })
    .catch(error => console.error('Error adding song:', error));
}

function showPlaylistsView() {
    console.log("showPlaylistsView called");
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showMainView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>All Playlists</h2>
        <div class="playlist-grid" id="all-playlists-container">
            ${playlists.map(playlist => `
                <div class="playlist-item" onclick="showPlaylistSongs('${playlist.name.replace(/'/g, "\\'")}')">
                    <img src="${playlist.image}" alt="${playlist.name}">
                    <p>${playlist.name}</p>
                </div>
            `).join('')}
        </div>
    `;
    attachControlPanelListeners();
}

function showSearchSongsView() {
    console.log("showSearchSongsView called");
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showMainView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Search Songs</h2>
        <form id="search-songs-form" class="search-songs-form">
            <input type="text" id="search-query" placeholder="Search for a song..." required>
            <button type="submit">Search</button>
        </form>
        <div id="search-results"></div>
    `;
    attachControlPanelListeners();
}

function handleSearchSongs(event) {
    event.preventDefault();
    const query = document.getElementById('search-query').value;
    fetch(`/search_youtube?query=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            const resultsContainer = document.getElementById('search-results');
            resultsContainer.innerHTML = '';
            data.results.forEach(result => {
                const div = document.createElement('div');
                div.className = 'search-result';
                div.innerHTML = `
                    <span>${result.title} - ${result.artist}</span>
                    <button onclick="addSearchedSong('${result.url}')">Add to Playlist</button>
                `;
                resultsContainer.appendChild(div);
            });
        })
        .catch(error => console.error('Error searching songs:', error));
}

function addSearchedSong(youtubeUrl) {
    console.log("addSearchedSong called with:", youtubeUrl);
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showMainView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Add Song</h2>
        <form id="add-song-form" class="add-song-form">
            <select name="playlist_name" id="add-song-playlist" required>
                <option value="">Select Playlist</option>
                ${playlists.map(playlist => `<option value="${playlist.name}">${playlist.name}</option>`).join('')}
            </select>
            <input type="text" name="youtube_url" id="youtube-url" value="${youtubeUrl}" placeholder="YouTube URL" required>
            <button type="submit">Add Song</button>
        </form>
    `;
    attachControlPanelListeners();
}

function showQueueView() {
    console.log("showQueueView called");
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <button class="back-btn" onclick="showMainView()"><i class="fas fa-arrow-left"></i> Back</button>
        <h2>Queue</h2>
        <button class="clear-queue-btn" onclick="clearQueue()">Clear Queue</button>
        <div class="queue-list" id="queue-container">
            ${songQueue.length === 0 ? '<p>No songs in queue.</p>' : songQueue.map((song, index) => `
                <div class="queue-item" draggable="true" data-id="${song.id}" data-index="${index}">
                    <i class="far fa-waveform"></i>
                    <span onclick="playSong(${song.id})" style="cursor: pointer;">${song.title} - ${song.artist}</span>
                    <button onclick="removeFromQueue(${index})"><i class="fas fa-trash"></i></button>
                </div>
            `).join('')}
        </div>
    `;
    attachControlPanelListeners();
    makeSortable();
}

function removeFromQueue(index) {
    console.log("removeFromQueue called with index:", index);
    if (index === currentSongIndex) {
        stopPlayer();
    } else if (index < currentSongIndex) {
        currentSongIndex--;
    }
    songQueue.splice(index, 1);
    originalQueue = [...songQueue];
    showQueueView();
}

function deletePlaylist(playlistId) {
    console.log("deletePlaylist called with:", playlistId);
    if (!confirm(`Are you sure you want to delete this playlist?`)) return;
    fetch('/delete_playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `playlist_id=${encodeURIComponent(playlistId)}`
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        selectedPlaylist = null;
        fetchPlaylists();
        showMainView();
    })
    .catch(error => console.error("Error deleting playlist:", error));
}

function deleteSong(songId) {
    console.log("deleteSong called with:", songId);
    if (!confirm("Are you sure you want to delete this song?")) return;
    fetch('/delete_song', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `song_id=${songId}`
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        fetchSongs();
        if (selectedPlaylist) showPlaylistSongs(selectedPlaylist);
    })
    .catch(error => console.error("Error deleting song:", error));
}

function makeSortable() {
    console.log("makeSortable called");
    const sortableList = document.getElementById('songs-container') || document.getElementById('queue-container');
    if (!sortableList) {
        console.warn("Sortable container not found!");
        return;
    }
    new Sortable(sortableList, {
        animation: 150,
        onEnd: (evt) => {
            const items = Array.from(sortableList.children);
            const newOrder = items.map((item, index) => ({
                id: item.dataset.id,
                index: parseInt(item.dataset.index) || index
            }));

            if (sortableList.id === 'songs-container' && selectedPlaylist) {
                const songIds = newOrder.map(item => parseInt(item.id));
                console.log("Reordering playlist:", selectedPlaylist, "New order:", songIds);
                fetch('/rearrange_playlist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `playlist_name=${encodeURIComponent(selectedPlaylist)}&song_ids=${songIds.join(',')}`
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to rearrange playlist: ' + response.statusText);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("Rearrange playlist success:", data.message);
                    fetchSongs();
                })
                .catch(error => {
                    console.error("Error rearranging playlist:", error);
                    alert("Failed to rearrange playlist: " + error.message);
                    showPlaylistSongs(selectedPlaylist); // Revert UI on failure
                });
            } else if (sortableList.id === 'queue-container') {
                songQueue = newOrder.map(item => 
                    allSongs.find(s => s.id === parseInt(item.id))
                ).filter(song => song !== undefined);
                currentSongIndex = songQueue.findIndex(s => s.id === songQueue[currentSongIndex]?.id);
                if (currentSongIndex === -1 && songQueue.length > 0) currentSongIndex = 0;
                originalQueue = [...songQueue];
                console.log("Reordered queue:", songQueue, "New index:", currentSongIndex);
                showQueueView();
            }
        }
    });
}

function fetchSongs() {
    console.log("fetchSongs called");
    fetch('/songs')
        .then(response => response.json())
        .then(data => {
            allSongs = data.songs.map(song => {
                console.log("Fetched song:", song);
                if (!song.url) {
                    console.warn("Song missing URL:", song);
                }
                return song;
            });
            console.log("Updated songs:", allSongs);
            if (selectedPlaylist) showPlaylistSongs(selectedPlaylist);
            else displaySongs();
        })
        .catch(error => console.error("Error fetching songs:", error));
}

function fetchPlaylists() {
    console.log("fetchPlaylists called");
    fetch('/playlists')
        .then(response => response.json())
        .then(data => {
            playlists = data.playlists;
            console.log("Updated playlists:", playlists);
            displayPlaylists();
        })
        .catch(error => console.error("Error fetching playlists:", error));
}

function displayPlaylists() {
    console.log("displayPlaylists called");
    const container = document.getElementById('playlists-container');
    if (!container) return;
    container.innerHTML = '';
    playlists.forEach(playlist => {
        const div = document.createElement('div');
        div.className = 'playlist-item';
        div.innerHTML = `
            <img src="${playlist.image}" alt="${playlist.name}">
            <p>${playlist.name}</p>
        `;
        div.addEventListener('click', () => {
            selectedPlaylist = playlist.name;
            showPlaylistSongs(playlist.name);
        });
        container.appendChild(div);
    });
}

function displaySongs() {
    console.log("displaySongs called");
    const container = document.getElementById('songs-container');
    if (!container) return;
    container.innerHTML = '';
    let filteredSongs = allSongs;
    if (selectedPlaylist) {
        filteredSongs = allSongs.filter(song => song.playlist === selectedPlaylist).sort((a, b) => a.position - b.position);
    }
    if (filteredSongs.length === 0) {
        container.innerHTML += '<p>No songs found in this playlist.</p>';
    } else {
        filteredSongs.forEach(song => {
            const songItem = document.createElement('div');
            songItem.className = 'song-item';
            songItem.draggable = true;
            songItem.dataset.id = song.id;
            songItem.dataset.songId = song.id;
            songItem.innerHTML = `
                <i class="far fa-waveform"></i>
                <span onclick="playSong(${song.id})" style="cursor: pointer;">${song.title} - ${song.artist}</span>
                <button onclick="addToQueue(${song.id})"><i class="fas fa-plus"></i></button>
                <button onclick="deleteSong(${song.id})" class="delete-btn"><i class="fas fa-trash"></i></button>
            `;
            container.appendChild(songItem);
        });
    }
    makeSortable();
}

function showMainView() {
    console.log("showMainView called");
    selectedPlaylist = null;
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `
        <div class="control-panel">
            <audio id="audio-player">
                <source id="audio-source" src="${audioPlayer.src}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="song-info">
                <span id="current-song-title">${document.getElementById('current-song-title').textContent}</span> - 
                <span id="current-song-artist">${document.getElementById('current-song-artist').textContent}</span>
            </div>
            <div class="player-controls">
                <button id="previous-btn" title="Previous Song"><i class="fas fa-step-backward"></i></button>
                <button id="play-pause" title="Play/Pause"><i class="fas fa-play"></i></button>
                <button id="next-btn" title="Next Song"><i class="fas fa-step-forward"></i></button>
                <button id="shuffle-btn" title="Toggle Shuffle"><i class="fas fa-random"></i></button>
            </div>
            <div class="player-progress">
                <span id="current-time">0:00</span>
                <input type="range" id="progress" min="0" max="100" value="0">
                <span id="duration">0:00</span>
            </div>
            <div class="player-volume">
                <i class="fas fa-volume-up"></i>
                <input type="range" id="volume" min="0" max="100" value="100">
            </div>
        </div>
        <div class="playlists">
            <h2>Playlists</h2>
            <div class="playlist-grid" id="playlists-container"></div>
        </div>
        <div class="songs">
            <h2>Songs</h2>
            <div class="song-list" id="songs-container"></div>
        </div>
    `;
    attachControlPanelListeners();
    displayPlaylists();
    displaySongs();
}

function updatePlayerUI() {
    console.log("updatePlayerUI called");
    const title = document.getElementById('current-song-title');
    const artist = document.getElementById('current-song-artist');
    if (!title || !artist) return;
    if (songQueue.length > 0 && currentSongIndex >= 0 && currentSongIndex < songQueue.length) {
        const currentSong = songQueue[currentSongIndex];
        title.textContent = currentSong.title;
        artist.textContent = currentSong.artist;
    } else {
        title.textContent = 'Select a song to play';
        artist.textContent = 'Artist';
    }
}

function handleDragStart(event) {
    event.dataTransfer.setData('text/plain', event.target.dataset.id);
}

function handleDragOver(event) {
    event.preventDefault();
}

function handleDrop(event) {
    event.preventDefault();
    const draggedId = event.dataTransfer.getData('text');
    const droppedOn = event.target.closest('.song-item') || event.target.closest('.queue-item');
    if (!droppedOn || draggedId === droppedOn.dataset.id) return;

    const container = droppedOn.parentNode;
    const allItems = Array.from(container.children);
    const draggedIndex = allItems.findIndex(item => item.dataset.id === draggedId);
    const droppedIndex = allItems.indexOf(droppedOn);

    if (draggedIndex < droppedIndex) {
        container.insertBefore(allItems[draggedIndex], droppedOn.nextSibling);
    } else {
        container.insertBefore(allItems[draggedIndex], droppedOn);
    }
    updateSongOrder(container.id);
}

function handleDragEnd() {
    // Cleanup if needed
}

function updateSongOrder(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const items = Array.from(container.children);
    const newOrder = items.map((item, index) => ({
        id: item.dataset.id,
        index: parseInt(item.dataset.index) || index
    }));

    if (containerId === 'songs-container' && selectedPlaylist) {
        const songIds = newOrder.map(item => parseInt(item.id));
        fetch('/rearrange_playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `playlist_name=${encodeURIComponent(selectedPlaylist)}&song_ids=${songIds.join(',')}`
        })
        .then(response => response.json())
        .then(data => {
            console.log(data.message);
            fetchSongs();
        })
        .catch(error => {
            console.error("Error rearranging playlist:", error);
            alert("Failed to rearrange playlist: " + error.message);
            showPlaylistSongs(selectedPlaylist);
        });
    } else if (containerId === 'queue-container') {
        songQueue = newOrder.map(item => 
            allSongs.find(s => s.id === parseInt(item.id))
        ).filter(song => song !== undefined);
        currentSongIndex = songQueue.findIndex(s => s.id === songQueue[currentSongIndex]?.id);
        if (currentSongIndex === -1 && songQueue.length > 0) currentSongIndex = 0;
        originalQueue = [...songQueue];
        showQueueView();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded - Initializing app");

    initAudioPlayer();
    attachControlPanelListeners();
    fetchSongs();
    fetchPlaylists();

    document.getElementById('show-playlists-btn').addEventListener('click', showPlaylistsView);
    document.getElementById('search-songs-btn').addEventListener('click', showSearchSongsView);
    document.getElementById('add-song-btn').addEventListener('click', addSong);
    document.getElementById('create-playlist-btn').addEventListener('click', createPlaylist);
    document.getElementById('queue-list-btn').addEventListener('click', showQueueView);

    document.addEventListener('submit', (event) => {
        if (event.target.id === 'create-playlist-form') handleCreatePlaylist(event);
        if (event.target.id === 'add-song-form') handleAddSong(event);
        if (event.target.id === 'search-songs-form') handleSearchSongs(event);
    });
});

console.log("Script loaded - End of file");