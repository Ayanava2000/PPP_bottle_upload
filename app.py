import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


# ============================================================
# SUPPLIER
# ============================================================

def get_supplier_name(supplier_id):
    suppliers = {
        "6": "Wiegand-Glas",
        "3": "Etivera",
        "4": "Systempack",
        "5": "Heinz-Glas",
        "7": "Gläser & Flaschen"
    }

    return suppliers.get(
        str(supplier_id),
        f"Unknown ({supplier_id})"
    )


# ============================================================
# GET BOTTLE DETAILS
# ============================================================

@st.cache_data(ttl=3600)
def get_bottle_params(headers, uuid):

    response = requests.get(
        f"https://ppp-configurator.packperform.com/api/v1/bottles/{uuid}",
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    return response.json()["data"]


# ============================================================
# BUILD FULL BOTTLE ROW
# ============================================================

@st.cache_data(ttl=3600)
def get_full_bottle(bottle):

    details = get_bottle_params(
        headers,
        bottle["uuid"]
    )

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    product_images = details.get("productImages") or []

    image_url = None

    if product_images:
        image_url = product_images[0].get("url")

    # --------------------------------------------------------
    # PRINTING AREAS
    # --------------------------------------------------------

    # IMPORTANT:
    # If printingAreas is [] then everything related to
    # printing areas is explicitly set to "No".

    printing_areas = details.get("printingAreas") or []

    if printing_areas:

        # First printing area
        pa = printing_areas[0] or {}

        pa_name = pa.get("name") or "No"
        pa_width = pa.get("width")
        pa_height = pa.get("height")
        pa_diameter = pa.get("diameter")

        if pa_width is None:
            pa_width = "No"

        if pa_height is None:
            pa_height = "No"

        if pa_diameter is None:
            pa_diameter = "No"

        has_printing_area = "🟢 Yes"

    else:

        pa_name = "No"
        pa_width = "No"
        pa_height = "No"
        pa_diameter = "No"

        has_printing_area = "🔴 No"

    # --------------------------------------------------------
    # SUPPLIER
    # --------------------------------------------------------

    supplier = get_supplier_name(
        details.get("supplierId")
    )

    # --------------------------------------------------------
    # RETURN ROW
    # --------------------------------------------------------

    return {

        # Basic
        "UUID": details.get("uuid"),
        "Name": details.get("name"),
        "Article No": details.get("supplierArticleNo"),

        # Image
        "Image URL": image_url,

        # Dimensions
        "Height": details.get("height"),
        "Diameter": details.get("diameter"),
        "Width": details.get("width"),
        "Depth": details.get("depth"),

        # Supplier
        "Supplier": supplier,

        # Image status
        "Has Image": (
            "🟢 Yes"
            if product_images
            else "🔴 No"
        ),

        # ----------------------------------------------------
        # PRINTING AREA
        # ----------------------------------------------------

        "Has Printing Area": has_printing_area,

        "PA Name": pa_name,
        "PA Width": pa_width,
        "PA Height": pa_height,
        "PA Diameter": pa_diameter,

        # ----------------------------------------------------
        # OTHER STATUS
        # ----------------------------------------------------

        "Has Price": (
            "🟢 Yes"
            if bottle.get("priceBundleId")
            else "🔴 No"
        ),

        "Has Lids": (
            "🟢 Yes"
            if bottle.get("lids")
            else "🔴 No"
        ),

        "Ready for Configuration": bottle.get(
            "isReadyForConfiguration"
        )
    }


# ============================================================
# LOAD BOTTLES
# ============================================================

@st.cache_data(ttl=300)
def load_bottles(headers):

    response = requests.get(
        "https://ppp-configurator.packperform.com/api/v1/bottles",
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    return response.json()["data"]


# ============================================================
# IMAGE QUALITY
# ============================================================

@st.cache_data
def check_image_quality(
    image_url,
    blur_threshold=0.4,
    min_width=500,
    min_height=500
):
    """
    Returns:
        {
            "quality": "Good" / "Low",
            "width": int,
            "height": int,
            "sharpness": float
        }

    or:

        "No Image"
    """

    if not image_url:
        return "No Image"

    try:

        # Download image
        resp = urlopen(
            image_url,
            timeout=20
        )

        image = np.asarray(
            bytearray(resp.read()),
            dtype=np.uint8
        )

        img = cv2.imdecode(
            image,
            cv2.IMREAD_COLOR
        )

        if img is None:
            return "Low"

        height, width = img.shape[:2]

        # ----------------------------------------------------
        # BLUR DETECTION
        # ----------------------------------------------------

        gray = cv2.cvtColor(
            img,
            cv2.COLOR_BGR2GRAY
        )

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


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Bottle Configuration Dashboard",
    layout="wide"
)


# ============================================================
# HEADER
# ============================================================

st.caption(
    f"Last refreshed: "
    f"{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
)

title_col, refresh_col = st.columns([8, 1])

with title_col:

    st.title(
        "Bottle Upload Backend Dashboard"
    )

with refresh_col:

    st.write("")
    st.write("")

    if st.button("🔄 Refresh"):

        # Clear ALL relevant caches
        load_bottles.clear()
        get_bottle_params.clear()
        get_full_bottle.clear()
        check_image_quality.clear()

        st.rerun()


# ============================================================
# API
# ============================================================

api_token = st.secrets["api_token"]
tenant_id = st.secrets["tenant_id"]

headers = {
    "Authorization": f"Bearer {api_token}",
    "X-Tenant-ID": tenant_id,
}


# ============================================================
# LOAD BOTTLES
# ============================================================

bottles = load_bottles(headers)


# ============================================================
# BUILD DATAFRAME
# ============================================================

progress_text = st.empty()

progress_text.info(
    "Loading bottle details..."
)

progress = st.progress(0)

rows = []

with ThreadPoolExecutor(
    max_workers=20
) as executor:

    for i, row in enumerate(
        executor.map(
            get_full_bottle,
            bottles
        )
    ):

        rows.append(row)

        progress.progress(
            (i + 1) / len(bottles)
        )


progress.empty()
progress_text.empty()


df = pd.DataFrame(rows)


# ============================================================
# KPI CARDS
# ============================================================

total = len(df)

ready = int(
    df["Ready for Configuration"].sum()
)

not_ready = total - ready


c1, c2, c3 = st.columns(3)

c1.metric(
    "Total Bottles",
    total
)

c2.metric(
    "Ready",
    ready
)

c3.metric(
    "Not Ready",
    not_ready
)


# ============================================================
# SUPPLIER OVERVIEW
# ============================================================

st.subheader(
    "Supplier Overview"
)


supplier_counts = (
    df["Supplier"]
    .value_counts()
)


supplier_totals = {
    "Wiegand-Glas": 970,
    "Etivera": 189,
    "Systempack": 225,
    "Heinz-Glas": 264,
    "Gläser & Flaschen": 385,
    "Unknown (None)": 3
}


supplier_order = [
    "Wiegand-Glas",
    "Etivera",
    "Systempack",
    "Heinz-Glas",
    "Gläser & Flaschen"
]


cols = st.columns(
    len(supplier_order)
)


for col, supplier in zip(
    cols,
    supplier_order
):

    uploaded = supplier_counts.get(
        supplier,
        0
    )

    supplier_total = supplier_totals.get(
        supplier,
        0
    )

    percent = (
        uploaded / supplier_total * 100
        if supplier_total
        else 0
    )

    col.metric(
        supplier,
        f"{uploaded}/{supplier_total}"
    )

    col.caption(
        f"{percent:.1f}% uploaded"
    )


st.divider()


# ============================================================
# TWO PANEL LAYOUT
# ============================================================

left, right = st.columns(
    [3, 1]
)


# ============================================================
# LEFT PANEL
# ============================================================

with left:

    # Hide fields that are only needed in the preview
    # from the main table.

    table_df = df.drop(
        columns=[
            "Image URL"
        ]
    )

    event = st.dataframe(
        table_df,
        width="stretch",
        hide_index=True,
        height=700,
        on_select="rerun",
        selection_mode="single-row"
    )


# ============================================================
# RIGHT PANEL
# ============================================================

with right:

    st.subheader(
        "Bottle Preview"
    )

    selected_rows = (
        event.selection.rows
    )

    if selected_rows:

        row = df.iloc[
            selected_rows[0]
        ]

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        st.markdown(
            f"### {row['Name']}"
        )


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        if row["Image URL"]:

            st.image(
                row["Image URL"],
                width="stretch"
            )

        else:

            st.warning(
                "No image available"
            )


        st.divider()


        # ----------------------------------------------------
        # BASIC DETAILS
        # ----------------------------------------------------

        st.markdown(
            "### Details"
        )

        st.write(
            f"**Supplier Article Number:** "
            f"{row['Article No']}"
        )

        st.write(
            f"**Height in mm:** "
            f"{row['Height']}"
        )

        st.write(
            f"**Diameter in mm:** "
            f"{row['Diameter']}"
        )

        st.write(
            f"**Width in mm:** "
            f"{row['Width']}"
        )

        st.write(
            f"**Depth in mm:** "
            f"{row['Depth']}"
        )

        st.write(
            f"**Supplier:** "
            f"{row['Supplier']}"
        )


        st.divider()


        # ----------------------------------------------------
        # PRINTING AREA
        # ----------------------------------------------------

        st.markdown(
            "### Printing Area"
        )

        st.write(
            f"**Printing Area:** "
            f"{row['Has Printing Area']}"
        )

        st.write(
            f"**PA Name:** "
            f"{row['PA Name']}"
        )

        st.write(
            f"**PA Width:** "
            f"{row['PA Width']}"
        )

        st.write(
            f"**PA Height:** "
            f"{row['PA Height']}"
        )

        st.write(
            f"**PA Diameter:** "
            f"{row['PA Diameter']}"
        )


        st.divider()


        # ----------------------------------------------------
        # IMAGE QUALITY
        # ----------------------------------------------------

        if row["Image URL"]:

            quality = check_image_quality(
                row["Image URL"]
            )

            if isinstance(
                quality,
                dict
            ):

                msg = (
                    f"Image Quality: "
                    f"{quality['quality']}\n\n"
                    f"Resolution: "
                    f"{quality['width']} × "
                    f"{quality['height']}\n\n"
                    f"Sharpness: "
                    f"{quality['sharpness']:.1f}"
                )

                if quality["quality"] == "Good":

                    st.success(
                        msg
                    )

                else:

                    st.error(
                        msg
                    )

            else:

                st.error(
                    f"Image Quality: {quality}"
                )

        else:

            st.warning(
                "No image available"
            )


        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        def badge(value):

            return (
                "🟢 Yes"
                if value == "🟢 Yes"
                else "🔴 No"
            )


        st.write(
            f"**Image:** "
            f"{badge(row['Has Image'])}"
        )

        st.write(
            f"**Printing Area:** "
            f"{badge(row['Has Printing Area'])}"
        )

        st.write(
            f"**Price:** "
            f"{badge(row['Has Price'])}"
        )

        st.write(
            f"**Lids:** "
            f"{badge(row['Has Lids'])}"
        )


        # ----------------------------------------------------
        # CONFIGURATION
        # ----------------------------------------------------

        ready_icon = (
            "🟢 Ready"
            if row["Ready for Configuration"]
            else "🔴 Not Ready"
        )

        st.write(
            f"**Configuration:** "
            f"{ready_icon}"
        )

    else:

        st.info(
            "Select a bottle from the table."
        )
