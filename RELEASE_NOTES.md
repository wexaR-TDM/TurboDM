# TurboDM release notes

What changed in each version, newest first. To download the latest version:
**[github.com/wexaR-TDM/TurboDM/releases/latest](https://github.com/wexaR-TDM/TurboDM/releases/latest)**
To update an installed TurboDM: *Help → Check for updates*. · [Türkçe sürüm notları](SURUM_NOTLARI.md)

<!-- Developer note: add a "## x.y.z" section at the top for every new version, in the same order as
     SURUM_NOTLARI.md. The update window shows the section of that version (build.ps1 puts it into latest.json). -->

## 1.7.32
• Refreshed app icon: the familiar blue circle and arrow are drawn more cleanly, and the line under the arrow is now split into parts (TurboDM downloads a file in parts). The same icon on the desktop, taskbar, setup wizard and browser extension

## 1.7.31
• Search box: type in the box in the page header to filter the list by file name (Ctrl+F opens it, Esc clears it)
• Speed panel: total speed, a speed graph of the last 60 seconds, the number of active downloads, time left, and queue start/stop and scheduler. If you don't want it, turn it off from the "More" menu
• Status bar: whether the browser extension is connected to TurboDM, free space in the download folder, total download speed and the version
• Plain numbers in the list (e.g. 337 / 512 MB), "–" in empty speed and time cells, when a download finished (e.g. today 14:32), an open folder button on paused downloads; refreshed icons and a select-all box in the header
• In a narrow window the title and buttons no longer disappear: the search box and button labels shrink first, and if needed the Speed and Time Left columns are hidden for the moment
• The window no longer freezes while reading the free space of a download folder on a network drive
(browser extension 1.7.8: tells TurboDM "I'm here" once a minute, so the connection status can be shown)

## 1.7.30
• Redesigned download list: each download takes two lines, with a file type icon, a bold file name, and the category and connection count below it. The Status column has a segmented progress bar showing each connection separately
• Row buttons: pause, resume, open folder, Retry and ⋯ for more actions, right on the row
• The list is grouped into Downloading, Waiting and Completed. If you don't want this, turn it off from the "More" menu or by right-clicking a column header
• Click a column header to sort: with groups on, each group is sorted on its own, and your choice is remembered
• The window opens larger (1280x720) the first time

## 1.7.29
• Redesigned main window: instead of the top toolbar, a "New Download" button on the left (its arrow offers batch downloads, torrents and magnets) and a clean sidebar; on the right, the title of the selected view, the download count and action buttons. Delete Completed, queue and scheduler actions are in the "More" menu; light and dark theme colors were refreshed too
• The Last Try, Description, Added and Finished columns are now hidden at first, leaving more room for file names. Right-click a column header to show them (your choice is kept)
• Fix: deleting the selected queue left an empty list; All Downloads is now shown

## 1.7.28
• Fix: if TurboDM closed or crashed right after the browser handed a download over to it, before the download started, the download could be lost. The extension now relaunches TurboDM; if TurboDM had saved the download it continues it, and if it hadn't (or can't be launched) the download is restarted in the browser (browser extension 1.7.7)
• Setup files of older versions are no longer deleted from GitHub (so links used by package managers such as winget keep working)

## 1.7.27
• In Chrome, Brave and Opera, the browser doesn't reload a manually installed extension by itself when TurboDM is updated, so the old extension kept running (e.g. the video button couldn't be moved). TurboDM now notices an outdated extension and tells you how to reload it: the reload (↻) button on the TurboDM card on the extensions page. The extension installed from the Edge store is updated by the store, so no warning is shown for it (browser extension 1.7.6)

## 1.7.26
• Fix: if the file of a paused download changed on the server (e.g. a new version was uploaded), parts of the old and new file could be joined and a corrupted file shown as "completed". The change is now detected and the file is downloaded again from the start; parts that the server sends from the wrong position are no longer written to the file
• Security: when a download is redirected to another site (e.g. a file hosting server), the session cookie from the browser is no longer sent there; browsers don't send it either
• Security: cookies of downloads that need a login are now stored in the download list with Windows encryption (only the same Windows user can read them)
• Fix: with "Shut down/sleep when the queue finishes" selected, the queue could be treated as finished, and the computer shut down, while a download was waiting for an automatic retry or being converted
• Fix: if a file with the same name appeared in the folder while a download was running, it was overwritten when the download finished. That file is now kept and the download is saved as "name (1)"

## 1.7.25
• Fix: on some sites (e.g. Twitch, Kick), when the site reloaded its player, the old video's "Download this video" button stayed on screen, several buttons appeared and the leftover button couldn't be closed with ×. Now there is a single button, on the largest visible video
• The video button can be dragged to any spot on the video; the chosen spot is remembered
• The video button no longer appears on live streams (TurboDM doesn't download live streams)
(browser extension 1.7.5)

## 1.7.24
• The browser extension is now in the Microsoft Edge Add-ons store: after TurboDM is installed, Edge offers the extension by itself and updates come from the store (https://microsoftedge.microsoft.com/addons/detail/dpeakjonbfgodlhkbpeekljfgnpbbjai)
• If the extension is installed twice (from the store and manually), downloads no longer reach TurboDM twice, and a download that TurboDM can't get and leaves to the browser is no longer grabbed and restarted over and over by the two copies (browser extension 1.7.4)
• Updated the extension setup guide with the store link

## 1.7.23
• Fix: when adding a video site link (e.g. a video address pasted by hand), pressing "Start Download" while the video was still being checked, or when no video was found, downloaded the site's web page instead of the video. The buttons now stay disabled until the video is found; if it can't be found, the reason is shown
• Updated the browser extension setup guide

## 1.7.22
• Downloads no longer appear in the browser first and get paused: while TurboDM is running, the browser's download panel doesn't open, the browser download is cancelled right away and the file goes straight to TurboDM
• Fix: if a download taken over by TurboDM can't start at all (e.g. the server allows the link only once and returns "HTTP 403"), the download is no longer lost: it is restarted in the browser and TurboDM shows the reason. Files TurboDM can't get at all (bot protection, etc.) also show up in the browser's download panel
(browser extension 1.7.3)

## 1.7.21
• Fix: when the server doesn't report the file size (e.g. photos downloaded from iCloud as a ZIP), the details showed a meaningless total such as "151 MB / 4194304 TB" and the percentage stayed at 0%. Now only the downloaded amount is shown, and the progress bar runs as a moving bar until the size is known

## 1.7.20
• Fix: download pages with a verification code (e.g. metin2.download) now go to TurboDM. On these sites the "Download" button submits a form and the site redirects to the file's real link; the extension wrongly left such downloads in the browser. If the file is the direct response to the form (e.g. subtitle sites), it still downloads in the browser (browser extension 1.7.2)

## 1.7.19
• Fix: before taking over a browser download, TurboDM checks that it can actually reach the file. On sites with bot protection such as Cloudflare (e.g. metin2.download), when the protection blocks TurboDM the download is no longer cancelled and lost: it continues in the browser and TurboDM shows the reason. The same applies to links that return a login or verification page (browser extension 1.7.1)

## 1.7.18
• Add many downloads at once (Tasks → Add multiple downloads…, Ctrl+Shift+N): paste a list of links or any text containing links; file names and sizes are checked, and the selected ones start right away or go to the chosen queue
• File verification: right-click a finished download → Verify file; MD5 / SHA-1 / SHA-256 are calculated and compared with the value given by the site
• The computer doesn't go to sleep while downloading (can be turned off in Options → General)
• Downloads stopped by a connection problem (drop, timeout, server error) are retried automatically; "not found" and disk errors are not retried
• Exit confirmation: asked when you press Exit while downloads are running
• Options → Connection: proxy server, custom browser identity (User-Agent), site logins (user name/password; passwords stored with Windows encryption)
• Multiple queues: add new queues in the Scheduler window, each with its own concurrent-download count and start/stop time; right-click → Add to queue
• Your own categories (Options → Categories): the extensions you specify are saved to their own folder
• Export/import the list (Tasks menu); hide columns by right-clicking the column header; new "Added" and "Finished" columns; total size of selected downloads
• Toggle the speed limit from the tray menu in one click; optionally apply the limit only while the computer is in use
• Browser extension 1.7.0: if TurboDM is closed, the extension opens it by itself and hands over the download

## 1.7.17
• Browser extension 1.6.4: downloads started by a form button (e.g. "Download subtitle" on subtitle sites) now stay in the browser. The server only serves these files with the form's data, so handing them to TurboDM produced a meaningless file such as "ind"

## 1.7.16
• Browser extension 1.6.3: the "Download this video" button no longer gets in the way while watching. If the mouse doesn't move for 3 seconds it fades out like the player's own controls and comes back when the mouse moves
• The × next to the button hides it on that page; it shows again when the page is reloaded (F5) or you move to another video

## 1.7.15
• Browser extension 1.6.2: fixed the "Extension context invalidated" error entry on the extensions page after the extension was updated or reloaded with tabs open; the old copy removes its buttons and stops quietly (the new version runs once the page is reloaded)

## 1.7.14
• Browser extension 1.6.1: if the page has a video, the extension window also lists "Video qualities"; clicking one opens TurboDM's save window with that quality selected (same as the menu over the video)

## 1.7.13
• Browser extension 1.6.0: new TurboDM theme. The extension window and the quality menu over videos use the program's colors and follow the browser's light/dark mode; toggle switches and a status label showing whether TurboDM is running
• The "Media on this page" section in the extension window appears only when a downloadable stream was found on the page (the empty "None. Try playing the video." text was removed)

## 1.7.12
• Smooth display in the details too: the connection bar and the "Downloaded" amounts in the connection list of the download window now advance smoothly instead of jumping
• In video downloads the "Receiving data" rows of the connection list are also shown in green

## 1.7.11
• Smooth display: percentage, downloaded amount, transfer rate and the progress bar in the download window and the list now advance smoothly instead of jumping (14.1%, 14.2%… instead of 14% → 18% → 23%); the speed no longer fluctuates on screen. Only the display changed, download speed is the same

## 1.7.10
• Browser extension 1.5.3: after the change in 1.7.8 the "Download this video" button didn't appear at all on some big video sites; fixed (the button still appears only on the video visible on screen)

## 1.7.9
• Fix: the "CERTIFICATE_VERIFY_FAILED: certificate has expired" error some computers got when downloading from sites like gofile. HTTPS certificates are now verified by Windows itself, like browsers do (Windows fetches newly needed root certificates automatically); security checks were not relaxed

## 1.7.8
• Browser extension 1.5.2: on pages like Instagram stories the "Download this video" button appears only on the video actually visible on screen (preloaded, hidden or clipped videos used to get buttons in empty areas)

## 1.7.7
• The text on the setup wizard's side image appears in the language chosen in setup

## 1.7.6
• Fix: the version shown in TurboDM.exe's file properties (Details) is now correct (it always said 1.0.0.0)
• Updated the feature line on the setup wizard's side image
• General cleanup of code and documents: unused code and texts removed, developer notes updated

## 1.7.5
• When the window is closed and the program goes to the system tray, the "The program keeps running in the background" notification is shown only the first time instead of every time

## 1.7.4
• Browser extension 1.5.1: closing a tab where a video was found no longer logs a "No tab with id" error on the extensions page (it was harmless and did not affect anything)

## 1.7.3
• Fix: the error status in the list ("Error: …") and the "retrying" info of video streams now also appear in the chosen language
• GitHub page: the English page shows English screenshots of the program

## 1.7.2
• The default language is the Windows language again (in setup and in the program); "System language (automatic)" option at the top of the Language menu

## 1.7.1
• Instant language switching: a fixed "Language" menu in the menu bar; menus, the list and open download windows switch without closing the program, downloads keep running
• English is the default language (in setup and in the program); choose the language at the start of setup or from the Language menu

## 1.7.0
• Language support: Türkçe, English, Deutsch, Français, Español, العربية (right-to-left layout), Italiano — Options → General → Language; the default is the Windows language
• Setup asks for the language first; the chosen language becomes the program's language. The setup and uninstall windows also use the chosen language
• Browser extension 1.5.0: 7 languages (follows the browser language)
• Release notes in the update window follow the program language (Turkish or English); the GitHub page and release notes are also available in English

## 1.6.4
• The update window explains what happens during an update: the program closes briefly, reopens in the taskbar when installation finishes, and active downloads continue where they left off

## 1.6.3
• Help → Release notes: the change notes of all versions on one page (also public on GitHub)

## 1.6.2
• TurboDM is now open source: GNU GPL v3 license; source code at github.com/wexaR-TDM/TurboDM
• The license text ships with the installer; the About window links to the license and source code

## 1.6.1
• Download windows are independent of the main window: they stay open when the main window is minimized

## 1.6.0
• Format choice: "Format" in the download window — MP4 (as is), MKV (lossless, fast), AVI (for older TVs/players), MP3 (audio only); conversion runs when the download finishes
• DASH (.mpd) video streams are supported
• Embedded players: the video is requested with the player's own page address and origin (for servers that return error 403)
• Browser extension 1.4.4: captures DASH streams and the address of embedded players

## 1.5.8
• New project repository address: github.com/wexaR-TDM/TurboDM (the old address redirects; updates are uninterrupted)
• License: the exact source code of the bundled ffmpeg is published on every release page; source details are in the ffmpeg folder
• Browser extension 1.4.3: project page link updated

## 1.5.7
• Security: updates are now digitally signed. TurboDM only installs updates signed by the developer; fake updates cannot be distributed
• Security: updates are downloaded only from the official GitHub release page

## 1.5.6
• Newly opened windows (download window, options, alerts) open in the exact center of the screen

## 1.5.5
• The server connection limit is not fixed: while a download runs smoothly, a new connection is tried about every 20 s; if the server allows it, speed increases and the new limit is saved

## 1.5.4
• Server connection limit (like IDM): if a server allows only a few connections (e.g. gofile), surplus connections back off without breaking the download; it continues with the working connections and speed fluctuates less
• A single connection failing repeatedly no longer stops the whole download; an error is shown only if no connection works
• The learned limit is saved: on resume, as many connections as the server allows are opened; it is shown in the download window
• The connection list shows the real cause of an error; "Retry-After" from the server is respected

## 1.5.3
• Simpler About window; the video component is called "Video engine" everywhere

## 1.5.2
• New TurboDM theme: follows Windows light/dark mode automatically and switches instantly while the program is open
• TurboDM-specific line icons, a toolbar with logo and name, a category menu with counts
• A thin progress line in the list's "Status" column; completed in green, failed in red
• Window title bars take the theme color (Windows 11)
• Options → General → Theme: Same as Windows / Light / Dark

## 1.5.1
• Bulk actions: checkboxes at the start of the list; clicking a box adds the row to the selection without disturbing others
• Header box to select all / clear selection; Ctrl+A and Esc shortcuts
• "Bulk selection" menu: select unfinished, completed, stopped, failed
• The context menu applies to all selected downloads (resume, stop, queue, copy addresses, delete)
• Fix: when the list refreshed, only the last row of a multi-selection remained

## 1.5.0
• Faster torrents: upload speed is limited automatically while downloading (a saturated upload line was slowing downloads)
• Torrent: connects to more peers faster, deeper piece request queue, multi-core piece verification
• Torrent: prefers encrypted connections and uses a random port instead of the well-known 6881 (against ISP throttling)
• Options → Torrent: "Limit upload speed automatically while downloading" setting
• After an update TurboDM reopens on its own (in the taskbar, without stealing focus); active downloads continue where they left off

## 1.4.9
• Browser extension 1.4.2: Turkish and English language support (the extension's name and description follow the browser language)

## 1.4.8
• Browser extension 1.4.1: TurboDM icon (toolbar and extensions page), store-ready package

## 1.4.7
• Browser extension 1.4.0: the "Download this video" button and quality menu now work on every site (Vimeo, Dailymotion, X and more)
• The extension passes the page's video to TurboDM, which finds the qualities; streams loaded by the page appear in the same menu
• "Open this page's video in TurboDM" button in the extension window for every page

## 1.4.6
• Updates now come via GitHub: new versions can be downloaded and installed with Help → Check for updates

## 1.4.5
• Downloads that were running during an update continue automatically where they left off once the update finishes

## 1.4.4
• Torrent: .torrent links are no longer saved as files but opened directly as torrents (file selection window)
• Torrent: on sites that only give the file to the browser (pages with a download button), the .torrent downloads in the browser and opens in TurboDM automatically (browser extension 1.3.2)
• If a site sends a web page instead of a torrent, TurboDM explains what to do instead of saving an .html file
• Minimize and maximize buttons in the download window; minimized windows go to the taskbar

## 1.4.3
• Uninstall: the empty 'Software\TurboDM' registry key is also removed (no traces left)

## 1.4.2
• Security: the browser bridge accepts requests only from the local address (DNS rebinding protection)
• Starting twice at the same time, or another program using the bridge port, no longer causes problems
• If the download list gets corrupted, it is recovered automatically from the previous good copy
• Disk space is checked before a download starts; disk/permission errors are reported immediately with a clear message
• Expired redirect addresses (cloud storage, GitHub, etc.) are refreshed automatically
• Very long file names and names forbidden in Windows (CON, NUL…) are corrected

## 1.4.1
• Fixed the long wait at the start of large downloads (e.g. a 22 GB 8K video): the temporary file is created as a sparse file
• TurboDM blue colors: the Windows accent color (e.g. red) no longer shows in the progress bar and tables
• 'Save folder' in the download window shows only the folder; the file name is set automatically

## 1.4.0
• IDM-style download window: connections and segmented progress bar in the lower section (Hide/Show details)
• New tab 'Speed limiter': a per-download speed limit that can be changed while downloading
• New tab 'When done': shut down / sleep / exit TurboDM (30 s countdown, can be cancelled)
• Scheduler: shut down / sleep / exit when the queue finishes

## 1.3.1
• Choosing a quality in the browser menu opens the save location window (quality and extension preselected; Download Later / Start Download is up to you)

## 1.3.0
• On YouTube the 'Download this video' button opens the quality menu on the page; the chosen quality downloads without further questions (like IDM)
• TurboDM's windows and alerts (download, completed, error) come to the front
• A front alert with a 'Retry' button on download errors

## 1.2.0
• YouTube downloads 2–3× faster: video and audio at the same time with 24 connections (IDM method)
• Fix: videos with special characters such as ™ in the title failed with "yt-dlp exit code 0"
• Expired stream addresses are refreshed automatically and the download continues where it left off
• Videos that were mistaken for errors in the previous version but actually downloaded are completed with "Resume" without downloading again
• The program name appears as "TurboDM" in Windows notifications
• Fix: Resume right after Pause could corrupt the file while a speed limit was on
• Fix: single-part downloads whose connection dropped early were counted as "completed" while incomplete

## 1.1.0
• Video downloads from YouTube and other sites (1080p/4K, audio only) — with the button over the video in the browser
• Help → Check for updates: TurboDM and the YouTube engine are updated from one window
• New TurboDM-themed setup wizard; installed version check and update mode
• Uninstall options: settings, unfinished downloads and downloaded files can be chosen separately

## 1.0.0
• First release: multi-connection downloads, FTP, HLS video, BitTorrent, browser extension
