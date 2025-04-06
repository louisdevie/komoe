# Sass plugin for Komoe

# Installation

`pip install komoe-sass`

You will also need to [install the Sass compiler](https://sass-lang.com/install).

# Setup

Add the following to your `komoe.toml`:

```toml
[plugin.sass]
package = "komoe_sass"
config.path = "style" # the directory where to look for .scss and .sass files
```
