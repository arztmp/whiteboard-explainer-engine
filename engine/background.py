"""Build a bottom-anchored background push using the normal drag timeline."""
from PIL import Image


def background_push(id_, source, sprite, tip, start, land, end, *,
                    stage=(1920, 1080), hand_height=300, inset=150):
    """Hand height and inset are design pixels at 1080p; preserve the PNG's alpha bounds."""
    width, height = stage
    with Image.open(sprite) as image:
        left, top, right, bottom = image.convert("RGBA").getchannel("A").point(lambda alpha: 255 if alpha > 16 else 0).getbbox()
    scale = hand_height * height / 1080 / (bottom-top)
    center = (left+right)/2
    contact_x = inset * width / 1920 + (tip["x"]-center)*scale
    contact_y = height - (bottom-tip["y"])*scale
    # The leading edge and the complete hand start off-screen to the right.
    initial_edge = width + 24
    return {
        "id": id_, "type": "image", "role": "background", "src": source,
        "x": initial_edge+width/2, "y": height/2, "w": width, "h": height,
        "fitImage": "cover", "enter": "none",
        "carry": {
            "mode": "drag", "handScale": scale,
            "grip": {"x": contact_x-width/2, "y": contact_y-height/2},
            "from": {"x": initial_edge+contact_x+100, "y": contact_y},
            "target": {"x": width/2, "y": height/2},
            "to": {"x": contact_x, "y": height+(tip["y"]-top)*scale+24},
            "start": start, "contact": start+.35, "pickup": start+.5,
            "land": land, "release": land, "end": end,
        },
    }, [left, top, right, bottom]
