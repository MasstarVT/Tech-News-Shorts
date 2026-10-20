import {loadFont} from "@remotion/fonts";
import bc600 from "@fontsource/barlow-condensed/files/barlow-condensed-latin-600-normal.woff2";
import bc700 from "@fontsource/barlow-condensed/files/barlow-condensed-latin-700-normal.woff2";
import bc800 from "@fontsource/barlow-condensed/files/barlow-condensed-latin-800-normal.woff2";
import bc900 from "@fontsource/barlow-condensed/files/barlow-condensed-latin-900-normal.woff2";
import bcx700 from "@fontsource/barlow-condensed/files/barlow-condensed-latin-ext-700-normal.woff2";
import bcx800 from "@fontsource/barlow-condensed/files/barlow-condensed-latin-ext-800-normal.woff2";
import b500 from "@fontsource/barlow/files/barlow-latin-500-normal.woff2";
import b600 from "@fontsource/barlow/files/barlow-latin-600-normal.woff2";

export const DISPLAY = "Barlow Condensed";
export const TEXT = "Barlow";

const LATIN_EXT = "U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF";

let started = false;

export const ensureFonts = () => {
  if (started) return;
  started = true;
  const faces: [string, string, string, string | undefined][] = [
    [DISPLAY, bc600, "600", undefined],
    [DISPLAY, bc700, "700", undefined],
    [DISPLAY, bc800, "800", undefined],
    [DISPLAY, bc900, "900", undefined],
    [DISPLAY, bcx700, "700", LATIN_EXT],
    [DISPLAY, bcx800, "800", LATIN_EXT],
    [TEXT, b500, "500", undefined],
    [TEXT, b600, "600", undefined],
  ];
  for (const [family, url, weight, unicodeRange] of faces) {
    loadFont({family, url, weight, unicodeRange}).catch((err) => {
      console.error(`Could not load ${family} ${weight}`, err);
    });
  }
};
