"""Fond d'image du DMG : « Glissez ReAble dans Applications ». Dessiné avec AppKit (installé avec pywebview).
Usage : python make_dmg_background.py sortie.png"""
import sys

from AppKit import (NSBezierPath, NSBitmapImageRep, NSColor, NSFont, NSFontAttributeName, NSForegroundColorAttributeName,
                    NSGraphicsContext, NSMakeRect, NSPNGFileType, NSString, NSCenterTextAlignment,
                    NSMutableParagraphStyle, NSParagraphStyleAttributeName)

W, H, SCALE = 660, 400, 2          # points ; l'image fait 1320 × 800 pixels (écrans Retina)


def text(s, y, size, weight_bold, color):
    ps = NSMutableParagraphStyle.alloc().init()
    ps.setAlignment_(NSCenterTextAlignment)
    font = NSFont.boldSystemFontOfSize_(size) if weight_bold else NSFont.systemFontOfSize_(size)
    NSString.stringWithString_(s).drawInRect_withAttributes_(
        NSMakeRect(0, y, W, size * 1.6), {NSFontAttributeName: font, NSForegroundColorAttributeName: color, NSParagraphStyleAttributeName: ps})


def main(out: str) -> None:
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, W * SCALE, H * SCALE, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0)
    rep.setSize_((W, H))
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.96, 0.96, 0.97, 1).setFill()
    NSBezierPath.fillRect_(NSMakeRect(0, 0, W, H))
    dark = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.12, 0.12, 0.13, 1)
    muted = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.40, 0.40, 0.43, 1)
    accent = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.04, 0.36, 0.83, 1)
    text("Glissez ReAble dans Applications", H - 70, 22, True, dark)
    text("Puis ouvrez-la depuis le dossier Applications.", H - 100, 13, False, muted)
    # flèche entre les deux icônes (centres à x=165 et x=495, y=190 depuis le haut → 210 depuis le bas)
    y = H - 190 - 6
    accent.setStroke(); accent.setFill()
    line = NSBezierPath.bezierPath(); line.setLineWidth_(5); line.setLineCapStyle_(1)
    line.moveToPoint_((250, y)); line.lineToPoint_((395, y)); line.stroke()
    head = NSBezierPath.bezierPath()
    head.moveToPoint_((415, y)); head.lineToPoint_((388, y + 15)); head.lineToPoint_((388, y - 15)); head.closePath(); head.fill()
    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, None).writeToFile_atomically_(out, True)


if __name__ == "__main__":
    main(sys.argv[1])
