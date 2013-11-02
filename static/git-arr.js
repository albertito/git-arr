/* Miscellaneous javascript functions for git-arr. */

/* Return the current timestamp. */
function now() {
    return (new Date().getTime() / 1000);
}

/* Return a human readable string telling "how long ago" for a timestamp. */
function how_long_ago(timestamp) {
    if (timestamp < 0)
        return "never";

	var seconds = Math.floor(now() - timestamp);

	var interval = Math.floor(seconds / (365 * 24 * 60 * 60));
	if (interval > 1)
		return interval + " years ago";

	interval = Math.floor(seconds / (30 * 24 * 60 * 60));
	if (interval > 1)
		return interval + " months ago";

	interval = Math.floor(seconds / (24 * 60 * 60));

	if (interval > 1)
		return interval + " days ago";
	interval = Math.floor(seconds / (60 * 60));

	if (interval > 1)
		return interval + " hours ago";

	interval = Math.floor(seconds / 60);
	if (interval > 1)
		return interval + " minutes ago";

    if (seconds > 1)
        return Math.floor(seconds) + " seconds ago";

    return "about now";
}

/* Go through the document and replace the contents of the span.age elements
 * with a human-friendly variant, and then show them. */
function replace_timestamps() {
    var elements = document.getElementsByClassName("age");
    for (var i = 0; i < elements.length; i++) {
        var e = elements[i];

        var timestamp = e.innerHTML;
        e.innerHTML = how_long_ago(timestamp);
        e.style.display = "inline";

        if (timestamp > 0) {
            var age = now() - timestamp;
            if (age < (2 * 60 * 60))
                e.className = e.className + " age-band0";
            else if (age < (3 * 24 * 60 * 60))
                e.className = e.className + " age-band1";
            else if (age < (30 * 24 * 60 * 60))
                e.className = e.className + " age-band2";
        }
    }
}
