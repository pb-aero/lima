// SPDX-License-Identifier: GPL-2.0
/*
 * Minimal bidirectional dummy ASoC codec.
 *
 * The in-tree dummies are one-directional: linux,spdif-dit declares .playback
 * only, linux,spdif-dir declares .capture only, and simple-audio-card takes
 * exactly one codec node (simple-card.c looks for a child named "codec"), so
 * neither pairing nor multi-codec gets you a full-duplex link.
 *
 * This declares ONE DAI with both directions and no hardware behind it, so a
 * simple-audio-card link over an I2S controller can transmit and capture at the
 * same time. Used to test RP1 I2S full-duplex loopback through an ADAU1860.
 */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/of.h>
#include <sound/soc.h>

#define DUP_RATES   (SNDRV_PCM_RATE_8000_192000 | SNDRV_PCM_RATE_KNOT)
#define DUP_FORMATS (SNDRV_PCM_FMTBIT_S16_LE | SNDRV_PCM_FMTBIT_S24_LE | \
		     SNDRV_PCM_FMTBIT_S32_LE)

static struct snd_soc_dai_driver dup_dai = {
	.name = "dummy-duplex-hifi",
	.playback = {
		.stream_name  = "Playback",
		.channels_min = 1,
		.channels_max = 8,
		.rates        = DUP_RATES,
		.formats      = DUP_FORMATS,
	},
	.capture = {
		.stream_name  = "Capture",
		.channels_min = 1,
		.channels_max = 8,
		.rates        = DUP_RATES,
		.formats      = DUP_FORMATS,
	},
};

static const struct snd_soc_dapm_widget dup_widgets[] = {
	SND_SOC_DAPM_OUTPUT("dup-out"),
	SND_SOC_DAPM_INPUT("dup-in"),
};

static const struct snd_soc_dapm_route dup_routes[] = {
	{ "dup-out", NULL, "Playback" },
	{ "Capture", NULL, "dup-in" },
};

static const struct snd_soc_component_driver dup_component = {
	.dapm_widgets     = dup_widgets,
	.num_dapm_widgets = ARRAY_SIZE(dup_widgets),
	.dapm_routes      = dup_routes,
	.num_dapm_routes  = ARRAY_SIZE(dup_routes),
	.idle_bias_on     = 1,
	.endianness       = 1,
};

static int dup_probe(struct platform_device *pdev)
{
	return devm_snd_soc_register_component(&pdev->dev, &dup_component,
					       &dup_dai, 1);
}

static const struct of_device_id dup_ids[] = {
	{ .compatible = "lima,dummy-duplex", },
	{ }
};
MODULE_DEVICE_TABLE(of, dup_ids);

static struct platform_driver dup_driver = {
	.probe = dup_probe,
	.driver = {
		.name = "dummy-duplex",
		.of_match_table = dup_ids,
	},
};
module_platform_driver(dup_driver);

MODULE_DESCRIPTION("Bidirectional dummy ASoC codec for I2S duplex testing");
MODULE_LICENSE("GPL");
