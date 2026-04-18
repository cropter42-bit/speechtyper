$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AssetsDir = Join-Path $ProjectRoot "assets"
New-Item -ItemType Directory -Force -Path $AssetsDir | Out-Null

Add-Type -AssemblyName System.Drawing

$size = 256
$bitmap = New-Object System.Drawing.Bitmap $size, $size
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)

$rect = New-Object System.Drawing.RectangleF 16, 16, 224, 224
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$radius = 58.0
$diameter = $radius * 2
$path.AddArc($rect.X, $rect.Y, $diameter, $diameter, 180, 90)
$path.AddArc($rect.Right - $diameter, $rect.Y, $diameter, $diameter, 270, 90)
$path.AddArc($rect.Right - $diameter, $rect.Bottom - $diameter, $diameter, $diameter, 0, 90)
$path.AddArc($rect.X, $rect.Bottom - $diameter, $diameter, $diameter, 90, 90)
$path.CloseFigure()

$bgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    (New-Object System.Drawing.Point 0, 0),
    (New-Object System.Drawing.Point $size, $size),
    ([System.Drawing.Color]::FromArgb(255, 21, 35, 63)),
    ([System.Drawing.Color]::FromArgb(255, 7, 15, 29))
)
$graphics.FillPath($bgBrush, $path)

$borderPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(90, 136, 196, 255)), 3
$graphics.DrawPath($borderPen, $path)

$bubbleBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    (New-Object System.Drawing.Point 48, 52),
    (New-Object System.Drawing.Point 184, 180),
    ([System.Drawing.Color]::FromArgb(255, 102, 244, 225)),
    ([System.Drawing.Color]::FromArgb(255, 70, 190, 255))
)
$bubbleRect = New-Object System.Drawing.RectangleF 48, 56, 132, 108
$graphics.FillEllipse($bubbleBrush, $bubbleRect)

$tailPoints = @(
    (New-Object System.Drawing.PointF 90, 145),
    (New-Object System.Drawing.PointF 74, 196),
    (New-Object System.Drawing.PointF 120, 160)
)
$graphics.FillPolygon($bubbleBrush, $tailPoints)

$innerBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 8, 20, 36))
$graphics.FillEllipse($innerBrush, (New-Object System.Drawing.RectangleF 66, 74, 96, 74))

$lineBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 233, 247, 255))
$graphics.FillRectangle($lineBrush, 88, 94, 50, 10)
$graphics.FillRectangle($lineBrush, 88, 114, 34, 10)

$caretBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    (New-Object System.Drawing.Point 140, 78),
    (New-Object System.Drawing.Point 205, 196),
    ([System.Drawing.Color]::FromArgb(255, 255, 255, 255)),
    ([System.Drawing.Color]::FromArgb(255, 205, 230, 255))
)
$caretPoints = @(
    (New-Object System.Drawing.PointF 164, 60),
    (New-Object System.Drawing.PointF 206, 60),
    (New-Object System.Drawing.PointF 188, 144),
    (New-Object System.Drawing.PointF 214, 144),
    (New-Object System.Drawing.PointF 150, 218),
    (New-Object System.Drawing.PointF 170, 132),
    (New-Object System.Drawing.PointF 146, 132)
)
$graphics.FillPolygon($caretBrush, $caretPoints)

$pngPath = Join-Path $AssetsDir "app-icon.png"
$icoPath = Join-Path $AssetsDir "app-icon.ico"
$bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)

$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream = [System.IO.File]::Create($icoPath)
$icon.Save($stream)
$stream.Close()

$graphics.Dispose()
$bgBrush.Dispose()
$bubbleBrush.Dispose()
$innerBrush.Dispose()
$lineBrush.Dispose()
$caretBrush.Dispose()
$borderPen.Dispose()
$path.Dispose()
$bitmap.Dispose()

Write-Host "Created:"
Write-Host "  $pngPath"
Write-Host "  $icoPath"
