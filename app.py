import streamlit as st
import requests
import pandas as pd
import cv2
import numpy as np

from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode
)


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
    # PPP ART NO
    # ========================================================

    # PPP Art No is taken from the detailed bottle response.
    #
    # Fallback to the bottle list response if necessary.

    ppp_art_no = (
        details.get("artNo")
        or bottle.get("artNo")
        or "No"
    )


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
        # PA image specifically uses configImageUrl.
        #

        pa_image = yes_no_badge(
            pa.get("configImageUrl")
        )

    else:

        # ----------------------------------------------------
        # NO PRINTING AREA
        # ----------------------------------------------------

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
        # IDENTIFICATION
        # ----------------------------------------------------

        "UUID": details.get("uuid"),

        "PPP Art No": ppp_art_no,

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

        # Clear all API/data caches
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

    "Gläser & Flaschen": 301,

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

    # --------------------------------------------------------
    # COLUMNS TO DISPLAY
    # --------------------------------------------------------

    display_columns = [

        "PPP Art No",

        "Name",

        "Article No",

        "Supplier",

        "Height",

        "Diameter",

        "Width",

        "Depth",

        "Volume",

        "Has Image",

        "Has Printing Area",

        "PA Name",

        "PA Width",

        "PA Height",

        "PA Image",

        "Has Price",

        "Has Lids",

        "Ready for Configuration"
    ]


    table_df = df[
        display_columns
    ].copy()


    # ========================================================
    # AGGRID CONFIGURATION
    # ========================================================

    gb = GridOptionsBuilder.from_dataframe(
        table_df
    )


    # --------------------------------------------------------
    # DEFAULT COLUMN SETTINGS
    # --------------------------------------------------------

    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        minWidth=90
    )


    # --------------------------------------------------------
    # COLUMN WIDTHS
    # --------------------------------------------------------

    gb.configure_column(
        "PPP Art No",
        width=125,
        pinned="left"
    )

    gb.configure_column(
        "Name",
        width=180
    )

    gb.configure_column(
        "Article No",
        width=140
    )

    gb.configure_column(
        "Supplier",
        width=140
    )

    gb.configure_column(
        "Height",
        width=100
    )

    gb.configure_column(
        "Diameter",
        width=105
    )

    gb.configure_column(
        "Width",
        width=95
    )

    gb.configure_column(
        "Depth",
        width=95
    )

    gb.configure_column(
        "Volume",
        width=95
    )

    gb.configure_column(
        "Has Image",
        width=110
    )

    # --------------------------------------------------------
    # PA COLUMNS
    # --------------------------------------------------------

    gb.configure_column(
        "Has Printing Area",
        width=145,
        headerClass="pa-header"
    )

    gb.configure_column(
        "PA Name",
        width=110,
        headerClass="pa-header"
    )

    gb.configure_column(
        "PA Width",
        width=105,
        headerClass="pa-header"
    )

    gb.configure_column(
        "PA Height",
        width=110,
        headerClass="pa-header"
    )

    gb.configure_column(
        "PA Image",
        width=105,
        headerClass="pa-header"
    )


    # --------------------------------------------------------
    # OTHER COLUMNS
    # --------------------------------------------------------

    gb.configure_column(
        "Has Price",
        width=105
    )

    gb.configure_column(
        "Has Lids",
        width=100
    )

    gb.configure_column(
        "Ready for Configuration",
        width=175
    )


    # --------------------------------------------------------
    # ROW SELECTION
    # --------------------------------------------------------

    gb.configure_selection(
        selection_mode="single",
        use_checkbox=False
    )


    # --------------------------------------------------------
    # GRID OPTIONS
    # --------------------------------------------------------

    grid_options = gb.build()


    # ========================================================
    # CUSTOM AGGRID CSS
    # ========================================================

    custom_css = {

        # PA headers
        ".pa-header": {
            "background-color": "#CBD5E1 !important",
            "color": "#111827 !important",
            "font-weight": "700 !important"
        },

        # Normal headers
        ".ag-header-cell": {
            "font-weight": "500"
        },

        # Header text
        ".ag-header-cell-text": {
            "font-size": "14px"
        },

        # Selected row
        ".ag-row-selected": {
            "background-color": "#E5E7EB !important"
        }
    }


    # ========================================================
    # RENDER AGGRID
    # ========================================================

    grid_response = AgGrid(

        table_df,

        gridOptions=grid_options,

        height=700,

        width="100%",

        update_mode=GridUpdateMode.SELECTION_CHANGED,

        allow_unsafe_jscode=False,

        custom_css=custom_css,

        theme="streamlit",

        fit_columns_on_grid_load=False,

        reload_data=False
    )


# ============================================================
# RIGHT PANEL
# ============================================================

with right:

    st.subheader(
        "Bottle Preview"
    )


    # --------------------------------------------------------
    # GET SELECTED ROW
    # --------------------------------------------------------

    selected_rows = (
        grid_response.get(
            "selected_rows",
            []
        )
    )


    selected_row = None


    if selected_rows is not None:

        if isinstance(
            selected_rows,
            pd.DataFrame
        ):

            if not selected_rows.empty:
                selected_row = (
                    selected_rows.iloc[0]
                )

        elif isinstance(
            selected_rows,
            list
        ):

            if len(selected_rows) > 0:
                selected_row = selected_rows[0]


    # --------------------------------------------------------
    # DISPLAY SELECTED BOTTLE
    # --------------------------------------------------------

    if selected_row is not None:

        selected_uuid = selected_row.get(
            "UUID"
        )

        # UUID is hidden from the table but available
        # in the original dataframe.

        matching_rows = df[
            df["PPP Art No"]
            == selected_row.get("PPP Art No")
        ]


        if not matching_rows.empty:

            row = matching_rows.iloc[0]


            # ------------------------------------------------
            # TITLE
            # ------------------------------------------------

            st.markdown(
                f"### {row['Name']}"
            )


            # ------------------------------------------------
            # PPP ART NO
            # ------------------------------------------------

            st.write(
                f"**PPP Art No:** "
                f"{row['PPP Art No']}"
            )


            # ------------------------------------------------
            # IMAGE
            # ------------------------------------------------

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


            # ------------------------------------------------
            # DETAILS
            # ------------------------------------------------

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


            # ------------------------------------------------
            # PRINTING AREA
            # ------------------------------------------------

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


            # ------------------------------------------------
            # IMAGE QUALITY
            # ------------------------------------------------

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


            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

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

    else:

        st.info(
            "Select a bottle from the table."
        )
