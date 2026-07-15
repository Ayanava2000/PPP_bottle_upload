import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np
from urllib.request import urlopen

from concurrent.futures import ThreadPoolExecutor

def get_supplier_name(supplier_id):
    suppliers = {
        "6": "Wiegand-Glas",
        "3": "Etivera",
        "4":"Systempack",
        "5": "Heinz-Glas",
        "7": "Gläser & Flaschen"
    }
    return suppliers.get(str(supplier_id), f"Unknown ({supplier_id})")

@st.cache_data(ttl=3600)
def get_full_bottle(bottle):
    details = get_bottle_params(headers, bottle["uuid"])



    image_url = None
    if details.get("productImages"):
        image_url = details["productImages"][0]["url"]
    supplier = get_supplier_name(details.get("supplierId"))

    print(supplier)

    return {
        "UUID": details.get("uuid"),
        "Name": details.get("name"),
        "Article No": details.get("supplierArticleNo"),
        "Image URL": image_url,
        "Height": details.get("height"),
        "Diameter": details.get("diameter"),
        "Width": details.get("width"),
        "Depth": details.get("depth"),
        "Supplier": supplier ,
        "Has Image": "🟢 Yes" if details.get("productImages") else "🔴 No",
        "Has Printing Area": "🟢 Yes" if details.get("printingAreas") else "🔴 No",
        "Has Price": "🟢 Yes" if bottle.get("priceBundleId") else "🔴 No",
        "Has Lids": "🟢 Yes" if bottle.get("lids") else "🔴 No",
        "Ready for Configuration": bottle.get("isReadyForConfiguration")
    }



@st.cache_data(ttl=300)
def load_bottles(headers):

    response = requests.get(
        "https://ppp-configurator.packperform.com/api/v1/bottles",
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    return response.json()["data"]


@st.cache_data(ttl=3600)
def get_bottle_params(headers, uuid):

    response = requests.get(
        f"https://ppp-configurator.packperform.com/api/v1/bottles/{uuid}",
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    return response.json()["data"]

@st.cache_data
def check_image_quality(image_url, blur_threshold=0.4, min_width=500, min_height=500):
    """
    Returns:
        "Okay"
        "Low (Resolution)"
        "Low (Blurry)"
        "No Image"
    """

    if not image_url:
        return "No Image"

    try:
        # Download image
        resp = urlopen(image_url)
        image = np.asarray(bytearray(resp.read()), dtype=np.uint8)

        img = cv2.imdecode(image, cv2.IMREAD_COLOR)

        if img is None:
            return "Low"

        height, width = img.shape[:2]

        # Resolution check

        #if width < min_width or height < min_height:
        #    return "Low"

        # Blur detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        sharpness = cv2.Laplacian(
            gray,
            cv2.CV_64F
        ).var()

        if sharpness < blur_threshold:
            return {
                "quality": "Low",
                "width": width,
                "height": height,
                "sharpness": float(sharpness)
            }

        return {
            "quality": "Good",
            "width": width,
            "height": height,
            "sharpness": float(sharpness)
        }

    except Exception:
        return "Low"

# ----------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------

st.set_page_config(
    page_title="Bottle Configuration Dashboard",
    layout="wide"
)

from datetime import datetime

st.caption(f"Last refreshed: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")

title_col, refresh_col = st.columns([8, 1])

with title_col:
    st.title("Bottle Upload Backend Dashboard")

with refresh_col:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh"):
        load_bottles.clear()
        st.rerun()

# ----------------------------------------------------
# API
# ----------------------------------------------------

api_token = st.secrets["api_token"]
tenant_id = st.secrets["tenant_id"]

headers = {
    "Authorization": f"Bearer {api_token}",
    "X-Tenant-ID": tenant_id,
}

bottles = load_bottles(headers)

# ----------------------------------------------------
# BUILD DATAFRAME
# ----------------------------------------------------



progress_text = st.empty()
progress_text.info("Loading bottle details...")

progress = st.progress(0)

with ThreadPoolExecutor(max_workers=20) as executor:

    rows = []

    for i, row in enumerate(executor.map(get_full_bottle, bottles)):
        rows.append(row)
        progress.progress((i + 1) / len(bottles))

progress.empty()
progress_text.empty()

df = pd.DataFrame(rows)


# ----------------------------------------------------
# KPI CARDS
# ----------------------------------------------------

total = len(df)
ready = df["Ready for Configuration"].sum()
not_ready = total - ready

c1, c2, c3 = st.columns(3)

c1.metric("Total Bottles", total)
c2.metric("Ready", ready)
c3.metric("Not Ready", not_ready)

supplier_counts = df["Supplier"].value_counts()

st.subheader("Supplier Overview")

supplier_totals = {
    "Wiegand-Glas": 2022,
    "Etivera": 504,
    "Systempack": 590,
    "Heinz-Glas": 264,
    "Gläser & Flaschen": 385,
    "Unknown (None)": 3
}

#supplier_counts = df["Supplier"].value_counts()



supplier_order = [
    "Wiegand-Glas",
    "Etivera",
    "Systempack",
    "Heinz-Glas",
    "Gläser & Flaschen"
]

cols = st.columns(len(supplier_order))

for col, supplier in zip(cols, supplier_order):

    uploaded = supplier_counts.get(supplier, 0)
    total = supplier_totals.get(supplier, 0)

    percent = uploaded / total * 100 if total else 0

    col.metric(
        supplier,
        f"{uploaded}/{total}"
        
    )
    col.caption(f"{percent:.1f}% uploaded")




st.divider()

# ----------------------------------------------------
# TWO PANEL LAYOUT
# ----------------------------------------------------

left, right = st.columns([3, 1])

# ---------------- LEFT ----------------

with left:
    event = st.dataframe(
        df.drop(columns=["Image URL"]),
        width="stretch",
        hide_index=True,
        height=700,
        on_select="rerun",
        selection_mode="single-row"
    )
# ---------------- RIGHT ----------------

with right:

    st.subheader("Bottle Preview")

    selected_rows = event.selection.rows

    if selected_rows:

        row = df.iloc[selected_rows[0]]

        details = get_bottle_params(
            headers,
            row["UUID"]
        )

        st.markdown(f"### {row['Name']}")

        if row["Image URL"]:
            st.image(
                row["Image URL"],
                width="stretch"
            )
        else:
            st.warning("No image available")

        st.divider()

        st.markdown("### Details")

        st.write(f"**Supplier Article Number:** {row["Article No"]}")
        st.write(f"**Height in mm:** {row["Height"]}")
        st.write(f"**Diameter in mm:** {row["Diameter"]}")
        st.write(f"**Width in mm:** {row["Width"]}")
        st.write(f"**Depth in mm:** {row["Depth"]}")
        st.write(f"**Supplier:** {row["Supplier"]}")

        st.divider()

        def badge(value):
            return "🟢 Yes" if value == "🟢 Yes" else "🔴 No"


        if row["Image URL"]:



            # Analyze image quality
            quality = check_image_quality(row["Image URL"])

            msg = (
                f"Image Quality: {quality['quality']}\n\n"
                f"Resolution: {quality['width']} × {quality['height']}\n\n"
                f"Sharpness: {quality['sharpness']:.1f}"
            )

            if quality["quality"] == "Good":
                st.success(msg)
            else:
                st.error(msg)

        else:
            st.warning("No image available")

        st.write(f"**Image:** {badge(row['Has Image'])}")
        st.write(f"**Printing Area:** {badge(row['Has Printing Area'])}")
        st.write(f"**Price:** {badge(row['Has Price'])}")
        st.write(f"**Lids:** {badge(row['Has Lids'])}")

        ready_icon = (
            "🟢 Ready"
            if row["Ready for Configuration"]
            else "🔴 Not Ready"
        )

        st.write(f"**Configuration:** {ready_icon}")

    else:

        st.info("Select a bottle from the table.")
