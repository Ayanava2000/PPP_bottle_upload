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
# YES / NO BADGE
# ============================================================

def yes_no_badge(value):
    """
    Returns:
        🟢 Yes -> value exists
        🔴 No  -> value is missing
    """

    if value is not None and value != "":
        return "🟢 Yes"

    return "🔴 No"


# ============================================================
# BOTTLE DETAILS API
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

    # ========================================================
    # PRODUCT IMAGES
    # ========================================================

    product_images = details.get("productImages") or []

    image_url = None

    if product_images:
        image_url = product_images[0].get("url")


    # ========================================================
    # PRODUCT SPECIFICATIONS
    # ========================================================

    height = details.get("height")
    diameter = details.get("diameter")
    width = details.get("width")
    depth = details.get("depth")
    volume = details.get("volume")


    # ========================================================
    # PRINTING AREAS
    # ========================================================

    printing_areas = details.get("printingAreas") or []

    if printing_areas:

        pa = printing_areas[0] or {}

        # ----------------------------------------------------
        # PRINTING AREA EXISTS
        # ----------------------------------------------------

        has_printing_area = "🟢 Yes"


        # ----------------------------------------------------
        # PA NAME
        # ----------------------------------------------------

        pa_name = yes_no_badge(
            pa.get("name")
        )


        # ----------------------------------------------------
        # PA WIDTH
        # ----------------------------------------------------

        pa_width = yes_no_badge(
            pa.get("width")
        )


        # ----------------------------------------------------
        # PA HEIGHT
        # ----------------------------------------------------

        pa_height = yes_no_badge(
            pa.get("height")
        )


        # ----------------------------------------------------
        # PA IMAGE
        # ----------------------------------------------------
        #
        # PA image is specifically determined by
        # configImageUrl.
        #

        config_image_url = pa.get(
            "configImageUrl"
        )

        pa_image = yes_no_badge(
            config_image_url
        )

    else:

        # ====================================================
        # NO PRINTING AREA
        # ====================================================
        #
        # If printingAreas == [], every PA specification
        # must be No.
        #

        has_printing_area = "🔴 No"

        pa_name = "🔴 No"
        pa_width = "🔴 No"
        pa_height = "🔴 No"
        pa_image = "🔴 No"


    # ========================================================
    # SUPPLIER
    # ========================================================

    supplier = get_supplier_name(
        details.get("supplierId")
    )


    # ========================================================
    # RETURN DATA
    # ========================================================

    return {

        # ----------------------------------------------------
        # BASIC INFORMATION
        # ----------------------------------------------------

        "UUID": details.get("uuid"),

        "Name": details.get("name"),

        "Article No": details.get(
            "supplierArticleNo"
        ),

        "Image URL": image_url,


        # ----------------------------------------------------
        # PRODUCT SPECIFICATIONS
        # ----------------------------------------------------
        #
        # Only Yes / No is displayed.
        #

        "Height": yes_no_badge(
            height
        ),

        "Diameter": yes_no_badge(
            diameter
        ),

        "Width": yes_no_badge(
            width
        ),

        "Depth": yes_no_badge(
            depth
        ),

        "Volume": yes_no_badge(
            volume
        ),


        # ----------------------------------------------------
        # SUPPLIER
        # ----------------------------------------------------

        "Supplier": supplier,


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

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

        "PA Image": pa_image,


        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        "Has Price": (
            "🟢 Yes"
            if bottle.get("priceBundleId")
            else "🔴 No"
        ),


        # ----------------------------------------------------
        # LIDS
        # ----------------------------------------------------

        "Has Lids": (
            "🟢 Yes"
            if bottle.get("lids")
            else "🔴 No"
        ),


        # ----------------------------------------------------
        # CONFIGURATION
        # ----------------------------------------------------

        "Ready for Configuration": (
            "🟢 Ready"
            if bottle.get(
                "isReadyForConfiguration"
            )
            else "🔴 Not Ready"
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

    if not image_url:
        return "No Image"

    try:

        # ----------------------------------------------------
        # DOWNLOAD IMAGE
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # RESOLUTION
        # ----------------------------------------------------

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


title_col, refresh_col = st.columns(
    [8, 1]
)


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

bottles = load_bottles(
    headers
)


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


df = pd.DataFrame(
    rows
)


# ============================================================
# KPI CARDS
# ============================================================

total = len(bottles)


ready = sum(
    bool(
        bottle.get(
            "isReadyForConfiguration"
        )
    )
    for bottle in bottles
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

    # Hide image URL from table.
    # It remains available for the preview.

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
        # DETAILS
        # ----------------------------------------------------

        st.markdown(
            "### Details"
        )


        st.write(
            f"**Supplier Article Number:** "
            f"{row['Article No']}"
        )


        st.write(
            f"**Height:** "
            f"{row['Height']}"
        )


        st.write(
            f"**Diameter:** "
            f"{row['Diameter']}"
        )


        st.write(
            f"**Width:** "
            f"{row['Width']}"
        )


        st.write(
            f"**Depth:** "
            f"{row['Depth']}"
        )


        st.write(
            f"**Volume:** "
            f"{row['Volume']}"
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
            f"**PA Image:** "
            f"{row['PA Image']}"
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

        st.write(
            f"**Image:** "
            f"{row['Has Image']}"
        )


        st.write(
            f"**Printing Area:** "
            f"{row['Has Printing Area']}"
        )


        st.write(
            f"**Price:** "
            f"{row['Has Price']}"
        )


        st.write(
            f"**Lids:** "
            f"{row['Has Lids']}"
        )


        st.write(
            f"**Configuration:** "
            f"{row['Ready for Configuration']}"
        )


    else:

        st.info(
            "Select a bottle from the table."
        )
