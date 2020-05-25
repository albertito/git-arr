
# git-arr - A git repository browser

[git-arr] is a [git] repository browser that can generate static HTML.

It is smaller, with less features and a different set of tradeoffs than
other similar software, so if you're looking for a robust and featureful git
browser, please look at [gitweb] or [cgit] instead.

However, if you want to generate static HTML at the expense of features, then
it's probably going to be useful.

It's open source under the MIT licence, please see the `LICENSE` file for more
information.

[git-arr]: https://blitiri.com.ar/p/git-arr/
[git]: https://git-scm.com/
[gitweb]: https://git-scm.com/docs/gitweb
[cgit]: https://git.zx2c4.com/cgit/about/


## Getting started

You will need [Python 3], and the [bottle.py] framework (the package is usually
called `python3-bottle` in most distributions).

If [pygments] is available, it will be used for syntax highlighting, otherwise
everything will work fine, just in black and white.


First, create a configuration file for your repositories. You can start by
copying `sample.conf`, which has the list of the available options.

Then, to generate the output to `/var/www/git-arr/` directory, run:

```sh
./git-arr --config config.conf generate --output /var/www/git-arr/
```

That's it!

The first time you generate, depending on the size of your repositories, it
can take some time. Subsequent runs should take less time, as it is smart
enough to only generate what has changed.

You can also use git-arr dynamically, although it's not its intended mode of
use, by running:

```
./git-arr --config config.conf serve
```

That can be useful when making changes to the software itself.


[Python 3]: https://www.python.org/
[bottle.py]: https://bottlepy.org/
[pygments]: https://pygments.org/


## Contact

If you want to report bugs, send patches, or have any questions or comments,
just let me know at albertito@blitiri.com.ar.

