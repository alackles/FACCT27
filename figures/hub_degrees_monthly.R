# Kirkley hub cut-offs on each calendar month's degree sequence.
#
#   Rscript figures/hub_degrees_monthly.R data/derived/2026-10-08/hubs \
#       data/derived/2026-10-08/figures/hub_degrees_monthly.png [in|out] [contexts|unweighted]
#
# Input is the output directory of `python -m facct27.hubs`: degrees_monthly.csv (one
# row per person x month x direction x weighting) for the points, and hubs.csv (monthly
# series) for each panel's N, M, h* and ER-wins flag. Defaults to in-degree,
# contexts-weighted; the other variants are separate files, not toggles. Plotting
# only: every number comes from the Python side. The PNG holds counts only, but is
# built from the corpus: keep it local.
# Written for R 4.3.3, ggplot2 3.5.0, dplyr 1.1.4, scales 1.3.0.

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
})

args <- commandArgs(trailingOnly = TRUE)
if (!length(args) %in% 2:4)
  stop("usage: Rscript hub_degrees_monthly.R <hubs dir> <out.png> [in|out] [contexts|unweighted]")
dir <- args[1]
direction_ <- if (length(args) >= 3) args[3] else "in"
weighting_ <- if (length(args) >= 4) args[4] else "contexts"
stopifnot(direction_ %in% c("in", "out"), weighting_ %in% c("contexts", "unweighted"))

d <- read.csv(file.path(dir, "degrees_monthly.csv")) |>
  filter(direction == direction_, weighting == weighting_)
h <- read.csv(file.path(dir, "hubs.csv")) |>
  filter(series == "monthly", direction == direction_, weighting == weighting_) |>
  mutate(er_wins = as.logical(er_wins), empty = as.logical(empty))

# Kirkley's hubs are the top h* by degree, so each cut-off sits between rank h* and h*+1.
cuts <- bind_rows(mutate(h, encoding = "ER", h = h_ER), mutate(h, encoding = "CM", h = h_CM)) |>
  select(window, encoding, h) |>
  filter(h > 0) |>
  mutate(encoding = factor(encoding, c("ER", "CM")))

# Each strip carries the month's size and h* for both encodings, so a cut-off is always
# read next to the volume it came from. (Inside the panel, labels collide with the lines.)
comma <- function(x) format(x, big.mark = ",", trim = TRUE)
strips <- h |>
  mutate(label = paste0(window, "\n",
                        ifelse(empty, "no edges",
                               paste0("N ", comma(N), " · M ", comma(M),
                                      " · h* ER ", h_ER, ", CM ", h_CM,
                                      ifelse(er_wins, "\nER compresses better", "")))))
strip_label <- setNames(strips$label, strips$window)

# Every month gets a panel, even one with no points to draw.
windows <- sort(unique(h$window))
d <- mutate(d, window = factor(window, windows))
cuts <- mutate(cuts, window = factor(window, windows))

p <- ggplot(filter(d, degree > 0), aes(rank, degree)) +
  geom_point(size = 0.9, alpha = 0.6, colour = "grey20", stroke = 0) +
  geom_vline(data = cuts, aes(xintercept = h + 0.5, linetype = encoding),
             linewidth = 0.4, colour = "grey10") +
  scale_x_log10(labels = scales::label_comma()) +
  scale_y_log10(labels = scales::label_comma()) +
  scale_linetype_manual(values = c(ER = "solid", CM = "22"), name = "Hub cut-off",
                        drop = FALSE) +
  facet_wrap(~window, ncol = 5, drop = FALSE, labeller = as_labeller(strip_label)) +
  labs(title = sprintf("Kirkley hubs month by month: %s-degree, %s",
                       direction_, ifelse(weighting_ == "contexts", "contexts-weighted",
                                          "unweighted")),
       subtitle = paste("Each panel is one calendar month (UTC); each point one person, by degree rank (log-log).",
                        "Axes are shared, so a panel's extent shows that month's volume.",
                        sep = "\n"),
       caption = paste("N = people in the month's graph, including those with degree 0 (not drawn on a log axis);",
                       "M = total degree. h* depends on how much data a month has, so compare cut-offs with N and M in view.",
                       sep = "\n"),
       x = "rank (1 = highest degree)", y = "degree") +
  theme_minimal(base_size = 10) +
  theme(panel.grid.minor = element_blank(),
        panel.grid.major = element_line(colour = "grey90", linewidth = 0.3),
        panel.border = element_rect(fill = NA, colour = "grey85", linewidth = 0.3),
        strip.text = element_text(size = 7.5, hjust = 0, lineheight = 1.05, colour = "grey15"),
        legend.position = "bottom",
        plot.caption = element_text(hjust = 0, colour = "grey40"),
        plot.title.position = "plot",
        plot.caption.position = "plot")

dir.create(dirname(args[2]), showWarnings = FALSE, recursive = TRUE)
ggsave(args[2], p, width = 11, height = 9, dpi = 200, bg = "white")
cat("wrote", args[2], "\n")
