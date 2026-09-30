// Panels are portalled out of the zoomed image so they keep their size and can flip
// into the page when a box sits near the image's edge. They sit above the page but
// below the app header (z-index 2) and dialogs, so a panel never covers the header.
export const PANEL_LAYER = 'z-[1]'
