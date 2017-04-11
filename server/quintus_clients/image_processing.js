

/*
  a processor class for getting canvas images
  canvasCtx: the canvas context (2d) object to process
  greyScale: true or false
  x/yStart/Stop: the positions of the rectangle to extract as image
 */
function CanvasProcessor(canvasCtx, greyScale, xStart, yStart, width, height) {
    this.canvasCtx = canvasCtx;
    this.greyScale = greyScale;
    this.xStart = xStart;
    this.yStart = yStart;
    this.width = width;
    this.height = height;

    // returns the processed image as an array of pixels
    // if greyScale:
    this.get_image() = function() {
        var data = this.canvasCtx.getImageData(this.xStart, this.yStart, width, height);
        // go through each pixel and convert from RGB into grey scale using the luminosity algorithm (0.21 R + 0.72 G + 0.07 B)
        if (true) { // this.greyScale) {
            var grey = [];
            for (var pix = 0; pix < data.length; pix += 4) {
                grey.push(data[pix] * 0.21 + data[pix+1] * 0.72 + data[pix+2] * 0.07); // ignore alpha channel
            }
            return grey;
        }
    };
}
