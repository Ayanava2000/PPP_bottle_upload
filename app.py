import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np

from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


# ============================================================
# SUPPLIER MAPPING
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
# GET COMPLETE BOTTLE DATA
# ============================================================

@st.cache_data(ttl=3600)
def get_full_bottle(bottle):

    details = get_bottle_params(
        headers,
        bottle["uuid"]
    )

    product_images = details.get("productImages") or []
    printing_areas = details.get("printingAreas") or []

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    image_url = None

    if product_images:
        image_url = product_images[0].get("url")

    # --------------------------------------------------------
    # SUPPLIER
    # --------------------------------------------------------

    supplier = get_supplier_name(
        details.get("supplierId")
    )

    # ========================================================
    # BASIC SPECIFICATION CHECKS
    # ========================================================

    has_volume = details.get("volume") is not None

    has_height = details.get("height") is not None

    has_diameter = details.get("diameter") is not None

    has_width = details.get("width") is not None

    has_depth = details.get("depth") is not None

    # --------------------------------------------------------
    # DIMENSIONS
    #
    # Either:
    #   diameter
    #
    # OR:
    #   width + depth
    # --------------------------------------------------------

    has_dimensions = (
        has_diameter
        or (has_width and has_depth)
    )

    # --------------------------------------------------------
    # PRODUCT IMAGE
    # --------------------------------------------------------

    has_image = bool(product_images)

    # --------------------------------------------------------
    # PRINTING AREA
    # --------------------------------------------------------

    has_printing_area = bool(printing_areas)

    # ========================================================
    # PRINTING AREA SPECIFICATIONS
    # ========================================================

    print_area_name_ok = True
    print_area_width_ok = True
    print_area_height_ok = True
    print_area_bottom_distance_ok = True
    print_area_type_ok = True
    print_area_config_image_ok = True

    for area in printing_areas:

        # Name
        if not area.get("name"):
            print_area_name_ok = False

        # Width
        if area.get("width") is None:
            print_area_width_ok = False

        # Height
        if area.get("height") is None:
            print_area_height_ok = False

        # Distance to bottom
        if area.get("bottomDistance") is None:
            print_area_bottom_distance_ok = False

        # Type
        #
        # API field is called printModes.
        # Example:
        # ["silkscreen", "digital"]
        #
        if not area.get("printModes"):
            print_area_type_ok = False

        # Configuration image
        if not area.get("configImageUrl"):
            print_area_config_image_ok = False

    # ========================================================
    # CONFIGURATION READINESS
    # ========================================================

    ready_for_configuration = (
        has_volume
        and has_height
        and has_dimensions
        and has_image
        and has_printing_area
        and print_area_name_ok
        and print_area_width_ok
        and print_area_height_ok
        and print_area_bottom_distance_ok
        and print_area_type_ok
        and print_area_config_image_ok
    )

    # ========================================================
    # RETURN TABLE DATA
    # ========================================================

    return {

        # ----------------------------------------------------
        # IDENTIFICATION
        # ----------------------------------------------------

        "UUID": details.get("uuid"),

        "Name": details.get("name"),

        "PPP Art No": details.get("artNo"),

        "Supplier Art No": details.get(
            "supplierArticleNo"
        ),

        # ----------------------------------------------------
        # BASIC SPECIFICATIONS
        # ----------------------------------------------------

        "Volume": (
            "🟢 Yes"
            if has_volume
            else "🔴 No"
        ),

        "Height": (
            "🟢 Yes"
            if has_height
            else "🔴 No"
        ),

        "Diameter": (
            "🟢 Yes"
            if has_diameter
            else "🔴 No"
        ),

        "Width": (
            "🟢 Yes"
            if has_width
            else "🔴 No"
        ),

        "Depth": (
            "🟢 Yes"
            if has_depth
            else "🔴 No"
        ),

        # ----------------------------------------------------
        # IMAGE / PRINTING AREA
        # ----------------------------------------------------

        "Image": (
            "🟢 Yes"
            if has_image
            else "🔴 No"
        ),

        "Print Area": (
            "🟢 Yes"
            if has_printing_area
            else "🔴 No"
        ),

        # ----------------------------------------------------
        # PRINTING AREA SPECIFICATIONS
        # ----------------------------------------------------

        "PA Name": (
            "🟢 Yes"
            if print_area_name_ok
            else "🔴 No"
        ),

        "PA Width": (
            "🟢 Yes"
            if print_area_width_ok
            else "🔴 No"
        ),

        "PA Height": (
            "🟢 Yes"
            if print_area_height_ok
            else "🔴 No"
        ),

        "PA Bottom Distance": (
            "🟢 Yes"
            if print_area_bottom_distance_ok
            else "🔴 No"
        ),

        "PA Type": (
            "🟢 Yes"
            if print_area_type_ok
            else "🔴 No"
        ),

        "PA Config Image": (
            "🟢 Yes"
            if print_area_config_image_ok
            else "🔴 No"
        ),

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

        # ----------------------------------------------------
        # CALCULATED CONFIGURATION STATUS
        # ----------------------------------------------------

        "Ready for Configuration": (
            ready_for_configuration
        ),

        # ----------------------------------------------------
        # INTERNAL DATA
        # ----------------------------------------------------

        "Image URL": image_url,

        "Supplier": supplier,
    }


# ============================================================
# LOAD ALL BOTTLES
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
            "width": ...,
            "height": ...,
            "sharpness": ...
        }

    or:

        "No Image"
    """

    if not image_url:
        return "No Image"

    try:

        # Download image
        resp = urlopen(image_url)

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
        # Resolution check
        #
        # Currently disabled because you only want to check
        # image existence in the table.
        # ----------------------------------------------------

        # if width < min_width or height < min_height:
        #     return {
        #         "quality": "Low",
        #         "width": width,
        #         "height": height,
        #         "sharpness": 0
        #     }

        # ----------------------------------------------------
        # Blur detection
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

total_bottles = len(df)

ready = int(
    df["Ready for Configuration"].sum()
)

not_ready = (
    total_bottles - ready
)


c1, c2, c3 = st.columns(3)

c1.metric(
    "Total Bottles",
    total_bottles
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

supplier_counts = (
    df["Supplier"].value_counts()
)

st.subheader(
    "Supplier Overview"
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
# LEFT: BOTTLE TABLE
# ============================================================

with left:

    table_columns = [

        "PPP Art No",

        "Supplier Art No",

        "Volume",

        "Height",

        "Diameter",

        "Width",

        "Depth",

        "Image",

        "Print Area",

        "PA Name",

        "PA Width",

        "PA Height",

        "PA Bottom Distance",

        "PA Type",

        "PA Config Image",

        "Has Price",

        "Has Lids",

        "Ready for Configuration",
    ]


    event = st.dataframe(

        df[table_columns],

        width="stretch",

        hide_index=True,

        height=700,

        on_select="rerun",

        selection_mode="single-row"
    )


# ============================================================
# RIGHT: BOTTLE PREVIEW
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
        # GET COMPLETE DETAILS AGAIN
        # ----------------------------------------------------

        details = get_bottle_params(
            headers,
            row["UUID"]
        )


        # ----------------------------------------------------
        # NAME
        # ----------------------------------------------------

        st.markdown(
            f"### {row['Name']}"
        )


        # ----------------------------------------------------
        # PRODUCT IMAGE
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


        # ====================================================
        # IDENTIFICATION
        # ====================================================

        st.markdown(
            "### Identification"
        )

        st.write(
            f"**PPP Article Number:** "
            f"{row['PPP Art No']}"
        )

        st.write(
            f"**Supplier Article Number:** "
            f"{row['Supplier Art No']}"
        )

        st.write(
            f"**Supplier:** "
            f"{row['Supplier']}"
        )


        st.divider()


        # ====================================================
        # ACTUAL SPECIFICATIONS
        # ====================================================

        st.markdown(
            "### Specifications"
        )

        st.write(
            f"**Volume:** "
            f"{details.get('volume')}"
        )

        st.write(
            f"**Height:** "
            f"{details.get('height')} mm"
        )

        st.write(
            f"**Diameter:** "
            f"{details.get('diameter')}"
        )

        st.write(
            f"**Width:** "
            f"{details.get('width')}"
        )

        st.write(
            f"**Depth:** "
            f"{details.get('depth')}"
        )


        st.divider()


        # ====================================================
        # PRINTING AREAS
        # ====================================================

        st.markdown(
            "### Printing Areas"
        )

        printing_areas = (
            details.get("printingAreas")
            or []
        )


        if not printing_areas:

            st.error(
                "🔴 No printing areas"
            )

        else:

            for i, area in enumerate(
                printing_areas,
                start=1
            ):

                st.markdown(
                    f"#### Printing Area {i}"
                )

                st.write(
                    f"**Name:** "
                    f"{area.get('name')}"
                )

                st.write(
                    f"**Width:** "
                    f"{area.get('width')}"
                )

                st.write(
                    f"**Height:** "
                    f"{area.get('height')}"
                )

                st.write(
                    f"**Distance to Bottom:** "
                    f"{area.get('bottomDistance')}"
                )

                st.write(
                    f"**Type:** "
                    f"{area.get('printModes')}"
                )


                config_image = (
                    area.get("configImageUrl")
                )


                if config_image:

                    st.write(
                        "**Configuration Image:** 🟢 Yes"
                    )

                    st.image(
                        config_image,
                        width="stretch"
                    )

                else:

                    st.write(
                        "**Configuration Image:** 🔴 No"
                    )


        st.divider()


        # ====================================================
        # IMAGE QUALITY
        # ====================================================

        st.markdown(
            "### Image Quality"
        )


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

                    st.success(msg)

                else:

                    st.error(msg)

            else:

                st.warning(
                    str(quality)
                )

        else:

            st.warning(
                "No image available"
            )


        # ====================================================
        # STATUS
        # ====================================================

        st.divider()

        st.markdown(
            "### Configuration Status"
        )


        st.write(
            f"**Image:** "
            f"{row['Image']}"
        )

        st.write(
            f"**Printing Area:** "
            f"{row['Print Area']}"
        )

        st.write(
            f"**Price:** "
            f"{row['Has Price']}"
        )

        st.write(
            f"**Lids:** "
            f"{row['Has Lids']}"
        )


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
