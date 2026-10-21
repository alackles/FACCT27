# Kirkley hub cut-offs on the whole-period degree sequences.
#
#   Rscript figures/hub_degrees.R data/derived/2026-10-08/hubs/degrees.csv \
#       data/derived/2026-10-08/figures/hub_degrees.png
#
# Input is degrees.csv from `python -m facct27.hubs` (one row per person x direction x
# weighting). Plotting only: every number comes from the Python side. The PNG holds
# counts only, but is built from the corpus: keep it local.
# Written for R 4.3.3, ggplot2 3.5.0, dplyr 1.1.4, scales 1.3.0.

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("usage: Rscript hub_degrees.R <degrees.csv> <out.png>")

d <- read.csv(args[1]) |>
  mutate(direction = factor(direction, c("in", "out"), c("in-degree", "out-degree")),
         weighting = factor(weighting, c("contexts", "unweighted"),
                            c("contexts-weighted", "unweighted")))

# Kirkley's hubs are the top h* by degree, so each cut-off sits between rank h* and h*+1.
# as.logical reads Python's True/False whether or not read.csv already converted them.
h <- d |>
  group_by(direction, weighting) |>
  summarise(ER = sum(as.logical(hub_ER)), CM = sum(as.logical(hub_CM)), .groups = "drop")
cuts <- bind_rows(mutate(h, encoding = "ER", h = ER), mutate(h, encoding = "CM", h = CM)) |>
  select(direction, weighting, encoding, h) |>
  filter(h > 0) |>
  mutate(encoding = factor(encoding, c("ER", "CM")),
         label = paste0(encoding, ": h* = ", h))

# Degree 0 can't sit on a log axis; say how many are left off in each panel.
counts <- d |>
  group_by(direction, weighting) |>
  summarise(note = sprintf("n = %s; degree 0 not shown: %s",
                           format(n(), big.mark = ","),
                           format(sum(degree == 0), big.mark = ",")), .groups = "drop")

p <- ggplot(filter(d, degree > 0), aes(rank, degree)) +
  geom_point(size = 1.2, alpha = 0.6, colour = "grey20", stroke = 0) +
  geom_vline(data = cuts, aes(xintercept = h + 0.5, linetype = encoding),
             linewidth = 0.5, colour = "grey10") +
  geom_text(data = cuts, aes(x = h + 0.5, y = Inf, label = label),
            angle = 90, hjust = 1.1, vjust = 1.4, size = 3, colour = "grey10") +
  geom_text(data = counts, aes(x = Inf, y = Inf, label = note), hjust = 1.02, vjust = 1.6,
            size = 2.8, colour = "grey40") +  # top right: always empty in a rank plot
  scale_x_log10(labels = scales::label_comma()) +
  scale_y_log10(labels = scales::label_comma()) +
  scale_linetype_manual(values = c(ER = "solid", CM = "22"), name = "Hub cut-off") +
  facet_grid(direction ~ weighting) +
  labs(title = "Kirkley hubs on the whole-period degree sequences",
       subtitle = "Each point is one person, by degree rank (log-log). Lines mark where each encoding stops counting hubs.",
       x = "rank (1 = highest degree)", y = "degree") +
  theme_minimal(base_size = 11) +
  theme(panel.grid.minor = element_blank(),
        panel.grid.major = element_line(colour = "grey90", linewidth = 0.3),
        strip.text = element_text(face = "bold"),
        legend.position = "bottom",
        plot.title.position = "plot")

dir.create(dirname(args[2]), showWarnings = FALSE, recursive = TRUE)
ggsave(args[2], p, width = 9, height = 6.5, dpi = 200, bg = "white")
cat("wrote", args[2], "\n")
