"""TurboDM temalı GitHub profil resmi (1024x1024 PNG). GitHub resmi daire şeklinde kırpar: önemli her şey
ortadaki dairenin içinde kalır. Çıktı: docs/avatar.png"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen,  # noqa: E402
                           QRadialGradient, QImage)

S = 1024


def main(out):
    app = QGuiApplication([])  # noqa: F841
    img = QImage(S, S, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    # koyu lacivert zemin (kurulum sihirbazı ve tema ile aynı aile)
    g = QLinearGradient(0, 0, S * 0.6, S)
    g.setColorAt(0, QColor("#0b1324"))
    g.setColorAt(1, QColor("#0f2a57"))
    p.fillRect(img.rect(), g)
    glow = QRadialGradient(S * 0.5, S * 0.42, S * 0.55)
    glow.setColorAt(0, QColor(59, 140, 240, 110))
    glow.setColorAt(1, QColor(59, 140, 240, 0))
    p.fillRect(img.rect(), glow)
    # hız çizgileri (sol)
    for i, (y, w, a) in enumerate(((0.40, 0.17, 150), (0.50, 0.23, 200), (0.60, 0.15, 120))):
        pen = QPen(QColor(120, 180, 255, a), S * 0.022)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(S * (0.16), S * y), QPointF(S * (0.16 + w), S * y))
    # uygulama simgesi (make_icon.render): simgedeki daire boyutun 60/64'ü
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from make_icon import render
    c, r = QPointF(S * 0.56, S * 0.5), S * 0.27
    size = int(round(2 * r * 64 / 60))
    p.drawImage(QPointF(c.x() - size / 2, c.y() - size / 2), render(size))
    p.end()
    img.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "docs", "avatar.png"))
