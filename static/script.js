console.log("Script loaded - Starting execution");

let audioPlayer;
let songQueue = [];
let currentSongIndex = -1;
let allSongs = [];
let playlists = [];
let selectedPlaylist = null;
let isShuffling = false;
let isRepeating = false;
let originalQueue = [];

function initAudioPlayer() {
    console.log("initAudioPlayer called");
    audioPlayer = new Audio();
    audioPlayer.addEventListener('ended', () => {
        if (songQueue.length > 0 && currentSongIndex + 1 < songQueue.length) {
            playNext(); // Queue has priority over repeat
        } else if (isRepeating) {
            audioPlayer.currentTime = 0;
            audioPlayer.play();
        } else {
            stopPlayer();
        }
    });
    audioPlayer.addEventListener('error', (e) => {
        console.error("Audio playback error:", e);
        document.getElementById('player-info').innerHTML = 'Error playing song, skipping...';
        playNext();
    });
    audioPlayer.addEventListener('loadeddata', () => {
        console.log("Audio loadeddata event");
        audioPlayer.play();
        updatePlayerUI();
    });
    audioPlayer.addEventListener('timeupdate', updateProgress);
    audioPlayer.addEventListener('play', () => document.getElementById('play-pause').innerHTML = '<i class="fas fa-pause"></i>');
    audioPlayer.addEventListener('pause', () => document.getElementById('play-pause').innerHTML = '<i class="fas fa-play"></i>');
}

function updateProgress() {
    const progress = document.getElementById('progress');
    const currentTime = document.getElementById('current-time');
    const duration = document.getElementById('duration');
    if (audioPlayer.duration) {
        progress.value = (audioPlayer.currentTime / audioPlayer.duration) * 100;
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
        return;
    }

    const playlistSongs = allSongs.filter(s => s.playlist === song.playlist).sort((a, b) => a.position - b.position);
    songQueue = playlistSongs;
    originalQueue = [...playlistSongs];
    currentSongIndex = playlistSongs.findIndex(s => s.id === song.id);
    if (isShuffling) {
        songQueue = smartShuffle(playlistSongs, song);
        currentSongIndex = songQueue.findIndex(s => s.id === song.id);
    }
    audioPlayer.src = song.url;
    audioPlayer.load();
    updatePlayerUI();
    renderQueue();
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
    renderQueue();
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
        renderQueue();
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
        renderQueue();
        console.log("Previous song:", prevSong, "Index:", currentSongIndex);
    }
}

function stopPlayer() {
    console.log("stopPlayer called");
    audioPlayer.pause();
    audioPlayer.src = '';
    document.getElementById('player-info').innerHTML = 'Select a song to play';
    document.querySelector('.player-controls').classList.remove('active');
    songQueue = [];
    originalQueue = [];
    currentSongIndex = -1;
    renderQueue();
    console.log("Player stopped");
}

function togglePlayPause() {
    console.log("togglePlayPause called");
    if (audioPlayer.paused) audioPlayer.play();
    else audioPlayer.pause();
}

function seek(event) {
    const progress = document.getElementById('progress');
    const seekPosition = (event.offsetX / progress.offsetWidth) * audioPlayer.duration;
    audioPlayer.currentTime = seekPosition;
}

function setVolume() {
    const volume = document.getElementById('volume');
    audioPlayer.volume = volume.value / 100;
}

function toggleShuffle() {
    console.log("toggleShuffle called");
    isShuffling = !isShuffling;
    const shuffleBtn = document.getElementById('shuffle-btn');
    shuffleBtn.classList.toggle('active', isShuffling);
    
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
    renderQueue();
    console.log("Shuffle toggled:", isShuffling, "Queue:", songQueue);
}

function toggleRepeat() {
    console.log("toggleRepeat called");
    isRepeating = !isRepeating;
    const repeatBtn = document.getElementById('repeat-btn');
    repeatBtn.classList.toggle('active', isRepeating);
    console.log("Repeat toggled:", isRepeating);
}

function smartShuffle(songs, currentSong) {
    let shuffled = [...songs];
    if (currentSong) {
        shuffled = shuffled.filter(s => s.id !== currentSong.id);
    }
    
    const artistGroups = {};
    shuffled.forEach(song => {
        if (!artistGroups[song.artist]) artistGroups[song.artist] = [];
        artistGroups[song.artist].push(song);
    });

    const result = [];
    const artists = Object.keys(artistGroups);
    while (shuffled.length > 0) {
        const artistIndex = Math.floor(Math.random() * artists.length);
        const artist = artists[artistIndex];
        if (artistGroups[artist].length > 0) {
            const songIndex = Math.floor(Math.random() * artistGroups[artist].length);
            result.push(artistGroups[artist][songIndex]);
            artistGroups[artist].splice(songIndex, 1);
            shuffled = shuffled.filter(s => s.id !== result[result.length - 1].id);
        }
        if (artistGroups[artist].length === 0) {
            artists.splice(artistIndex, 1);
        }
    }

    if (currentSong) {
        result.unshift(currentSong);
    }
    return result;
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
    renderQueue();
    console.log("Playing playlist:", playlistName, "Queue:", songQueue);
}

function renderQueue() {
    console.log("renderQueue called");
    const queueList = document.getElementById('queue-list');
    queueList.innerHTML = '<h3>Queue</h3>';
    if (songQueue.length === 0) {
        queueList.innerHTML += '<p>No songs in queue.</p>';
    } else {
        queueList.innerHTML += '<button onclick="clearQueue()" class="clear-queue-btn">Clear Queue</button>';
        songQueue.forEach((song, index) => {
            const queueItem = document.createElement('div');
            queueItem.className = 'queue-item';
            queueItem.innerHTML = `
                <span ${index === currentSongIndex ? 'style="font-weight: bold; color: #1db954;"' : ''}>${song.title} - ${song.artist}</span>
                <button onclick="playSong(${song.id})"><i class="fas fa-play"></i></button>
            `;
            queueList.appendChild(queueItem);
        });
    }
}

function clearQueue() {
    console.log("clearQueue called");
    // Preserve the current song if one is playing
    let currentSong = null;
    if (songQueue.length > 0 && currentSongIndex >= 0 && currentSongIndex < songQueue.length) {
        currentSong = songQueue[currentSongIndex];
    }

    // Clear the queue and original queue
    songQueue = [];
    originalQueue = [];

    // If a song is currently playing, add it back as the only song in the queue
    if (currentSong) {
        songQueue = [currentSong];
        originalQueue = [currentSong];
        currentSongIndex = 0;
    } else {
        currentSongIndex = -1;
    }

    // Update the UI
    renderQueue();
    updatePlayerUI();
    console.log("Queue cleared. Current song:", currentSong, "Queue:", songQueue);
}

function showEditPlaylistPopup(playlistId, playlistName) {
    console.log("showEditPlaylistPopup called with:", playlistId, playlistName);
    if (!playlistId) {
        alert("Cannot edit this playlist. Please create it through the interface.");
        return;
    }
    const existingPopup = document.getElementById('edit-playlist-popup');
    if (existingPopup) existingPopup.remove();

    const popup = document.createElement('div');
    popup.id = 'edit-playlist-popup';
    popup.className = 'edit-playlist-popup';
    popup.innerHTML = `
        <div class="popup-content">
            <h3>Edit Playlist</h3>
            <button onclick="updatePlaylistImage(${playlistId})">Change Image</button>
            <button onclick="renamePlaylist(${playlistId}, '${playlistName.replace(/'/g, "\\'")}')">Rename Playlist</button>
            <button onclick="document.getElementById('edit-playlist-popup').remove()">Cancel</button>
        </div>
    `;
    document.body.appendChild(popup);
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
                renderPlaylists();
                document.getElementById('edit-playlist-popup')?.remove();
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
    if (newName === null) {
        document.getElementById('edit-playlist-popup')?.remove();
        return;
    }

    fetch('/rename_playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `playlist_id=${encodeURIComponent(playlistId)}&new_name=${encodeURIComponent(newName)}`
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || 'Rename failed'); });
        }
        return response.json();
    })
    .then(data => {
        alert(data.message);
        renderPlaylists();
        if (selectedPlaylist === currentName) {
            selectedPlaylist = newName;
            showPlaylistSongs(newName);
        }
        document.getElementById('edit-playlist-popup')?.remove();
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
    const songList = document.getElementById('song-list');
    songList.innerHTML = `
        <div class="playlist-header">
            <button onclick="showMainPage()" class="back-btn"><i class="fas fa-arrow-left"></i></button>
            <h2>Songs in ${playlistName}</h2>
            <button onclick="deletePlaylist(${playlists.find(p => p.name === playlistName).id})" class="delete-btn"><i class="fas fa-trash"></i></button>
        </div>
        <ul id="sortable-songs" class="sortable">`;
    if (playlistSongs.length === 0) {
        songList.innerHTML += '<p>No songs found in this playlist.</p>';
    } else {
        playlistSongs.forEach(song => {
            const songItem = document.createElement('li');
            songItem.className = 'song-item';
            songItem.dataset.id = song.id;
            songItem.dataset.songId = song.id;
            songItem.innerHTML = `
                <span onclick="playSong(${song.id})" style="cursor: pointer;">${song.title} - ${song.artist}</span>
                <button onclick="addToQueue(${song.id})"><i class="fas fa-plus"></i></button>
                <button onclick="playPlaylist('${playlistName.replace(/'/g, "\\'")}')"><i class="fas fa-list-play"></i></button>
                <button onclick="deleteSong(${song.id})" class="delete-btn"><i class="fas fa-trash"></i></button>
            `;
            songList.querySelector('#sortable-songs').appendChild(songItem);
        });
    }
    songList.innerHTML += '</ul>';
    makeSortable();
}

function createPlaylist() {
    console.log("createPlaylist called");
    const playlistName = document.getElementById('new-playlist-name').value;
    if (!playlistName) {
        alert("Playlist name is empty. Proceeding to create playlist with empty name.");
    }

    fetch('/create_playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `playlist_name=${encodeURIComponent(playlistName)}`
    })
    .then(response => {
        if (!response.ok) throw new Error('Playlist creation failed');
        return response.json();
    })
    .then(data => {
        alert(data.message);
        document.getElementById('new-playlist-name').value = '';
        renderPlaylists();
    })
    .catch(error => {
        console.error("Error creating playlist:", error);
        alert("Failed to create playlist: " + error.message);
    });
}

function addSongFromUrl(youtubeUrl, playlistName) {
    console.log("addSongFromUrl called with:", youtubeUrl, playlistName);
    if (!youtubeUrl || !playlistName) {
        alert("Please select a playlist.");
        return;
    }

    fetch('/add_song', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `playlist_name=${encodeURIComponent(playlistName)}&youtube_url=${encodeURIComponent(youtubeUrl)}`
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        indexSongs();
        if (selectedPlaylist === playlistName) showPlaylistSongs(playlistName);
    })
    .catch(error => {
        console.error("Error adding song:", error);
        alert("Failed to add song. Check the URL and try again.");
    });
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
        renderPlaylists();
        showMainPage();
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
        indexSongs();
        if (selectedPlaylist) showPlaylistSongs(selectedPlaylist);
    })
    .catch(error => console.error("Error deleting song:", error));
}

function makeSortable() {
    console.log("makeSortable called");
    const sortableList = document.getElementById('sortable-songs');
    if (!sortableList) return;
    Sortable.create(sortableList, {
        animation: 150,
        onEnd: (evt) => {
            const songIds = Array.from(sortableList.children).map(item => item.dataset.id);
            fetch('/rearrange_playlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `playlist_name=${encodeURIComponent(selectedPlaylist)}&song_ids=${songIds.join(',')}`
            })
            .then(response => response.json())
            .then(data => {
                console.log(data.message);
                indexSongs();
            })
            .catch(error => console.error("Error rearranging playlist:", error));
        }
    });
}

function indexSongs() {
    console.log("indexSongs called");
    fetch('/songs')
        .then(response => response.json())
        .then(data => {
            allSongs = data.songs;
            console.log("Updated songs:", allSongs);
        })
        .catch(error => console.error("Error indexing songs:", error));
}

function updatePlayerUI() {
    console.log("updatePlayerUI called");
    console.log("songQueue:", songQueue, "currentSongIndex:", currentSongIndex);
    const playerInfo = document.getElementById('player-info');
    const playerControls = document.querySelector('.player-controls');
    if (songQueue.length > 0 && currentSongIndex >= 0 && currentSongIndex < songQueue.length) {
        const currentSong = songQueue[currentSongIndex];
        console.log("Current song:", currentSong);
        playerInfo.innerHTML = `${currentSong.title} - ${currentSong.artist}`;
        playerControls.classList.add('active');
    } else {
        playerInfo.innerHTML = 'Select a song to play';
        playerControls.classList.remove('active');
    }
}

function renderPlaylists() {
    console.log("renderPlaylists called");
    fetch('/playlists')
        .then(response => response.json())
        .then(data => {
            playlists = data.playlists;
            console.log("Playlists:", playlists);
            const playlistContainer = document.getElementById('playlists');
            playlistContainer.innerHTML = `
                <h2>Playlists</h2>
                <div class="add-playlist">
                    <input type="text" id="new-playlist-name" placeholder="New Playlist">
                    <button onclick="createPlaylist()"><i class="fas fa-plus"></i></button>
                </div>`;
            playlists.forEach(playlist => {
                const playlistDiv = document.createElement('div');
                playlistDiv.className = 'playlist-item';
                playlistDiv.innerHTML = `
                    <img src="${playlist.image}" alt="${playlist.name}" class="playlist-image" onclick="showEditPlaylistPopup(${playlist.id}, '${playlist.name.replace(/'/g, "\\'")}')">
                    <button class="playlist-name" onclick="showPlaylistSongs('${playlist.name.replace(/'/g, "\\'")}')">${playlist.name}</button>
                `;
                playlistContainer.appendChild(playlistDiv);
            });

            const playlistSelect = document.getElementById('playlist-select');
            if (playlistSelect) {
                playlistSelect.innerHTML = '<option value="">Select Playlist</option>';
                playlists.forEach(playlist => {
                    const option = document.createElement('option');
                    option.value = playlist.name;
                    option.textContent = playlist.name;
                    playlistSelect.appendChild(option);
                });
            }
        })
        .catch(error => console.error("Error rendering playlists:", error));
}

function showMainPage() {
    console.log("showMainPage called");
    selectedPlaylist = null;
    const songList = document.getElementById('song-list');
    songList.innerHTML = `
        <h2>Songs</h2>
        <p>Select a playlist to view songs.</p>
        <div class="add-song">
            <input type="text" id="youtube-url" placeholder="YouTube URL">
            <select id="playlist-select"></select>
            <button onclick="addSongFromUrl(document.getElementById('youtube-url').value, document.getElementById('playlist-select').value)"><i class="fas fa-download"></i></button>
        </div>`;
    renderPlaylists();
}

function search() {
    console.log("search called");
    const query = document.getElementById('search-input').value.trim().toLowerCase();
    if (!query) {
        showMainPage();
        return;
    }

    const matchingPlaylists = playlists.filter(p => p.name.toLowerCase().includes(query));
    const matchingSongs = allSongs.filter(s => 
        s.title.toLowerCase().includes(query) || s.artist.toLowerCase().includes(query)
    );

    fetch(`/search_youtube?query=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(youtubeData => {
            const songList = document.getElementById('song-list');
            songList.innerHTML = '<h2>Search Results</h2>';

            if (matchingPlaylists.length > 0) {
                songList.innerHTML += '<h3>Playlists</h3>';
                matchingPlaylists.forEach(playlist => {
                    const item = document.createElement('div');
                    item.className = 'song-item';
                    item.innerHTML = `
                        <img src="${playlist.image}" alt="${playlist.name}" class="playlist-image" onclick="showEditPlaylistPopup(${playlist.id}, '${playlist.name.replace(/'/g, "\\'")}')">
                        <span>${playlist.name}</span>
                        <button onclick="showPlaylistSongs('${playlist.name.replace(/'/g, "\\'")}')"><i class="fas fa-folder"></i></button>
                    `;
                    songList.appendChild(item);
                });
            }

            if (matchingSongs.length > 0) {
                songList.innerHTML += '<h3>Local Songs</h3>';
                matchingSongs.forEach(song => {
                    const item = document.createElement('div');
                    item.className = 'song-item';
                    item.innerHTML = `
                        <span onclick="playSong(${song.id})" style="cursor: pointer;">${song.title} - ${song.artist} (${song.playlist})</span>
                        <button onclick="addToQueue(${song.id})"><i class="fas fa-plus"></i></button>
                    `;
                    songList.appendChild(item);
                });
            }

            if (youtubeData.results.length > 0) {
                songList.innerHTML += '<h3>YouTube Results</h3>';
                youtubeData.results.forEach(video => {
                    const item = document.createElement('div');
                    item.className = 'song-item';
                    item.innerHTML = `
                        <span>${video.title} - ${video.artist}</span>
                        <select class="youtube-playlist-select" onchange="addSongFromUrl('${video.url}', this.value)">
                            <option value="">Add to Playlist</option>
                            ${playlists.map(p => `<option value="${p.name}">${p.name}</option>`).join('')}
                        </select>
                    `;
                    songList.appendChild(item);
                });
            }

            if (matchingPlaylists.length === 0 && matchingSongs.length === 0 && youtubeData.results.length === 0) {
                songList.innerHTML += '<p>No results found.</p>';
            }
        })
        .catch(error => console.error("Error searching:", error));
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded - Initializing app");
    initAudioPlayer();
    renderPlaylists();
    fetch('/songs')
        .then(response => response.json())
        .then(data => {
            allSongs = data.songs;
            console.log("Initial songs:", allSongs);
            showMainPage();
            renderQueue();
        })
        .catch(error => console.error("Error fetching songs:", error));

    // Add Enter key event listener for search
    document.getElementById('search-input').addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            search();
        }
    });
});

console.log("Script loaded - End of file");