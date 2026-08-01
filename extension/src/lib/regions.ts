/**
 * Province/state options for the signup region select.
 *
 * Codes are ISO 3166-2 ("CA-ON", "US-CA") and are stored in the user's Supabase
 * metadata as `region`, then sent with analyze requests for region-aware origin
 * research (the same product is sourced differently per region).
 */
export interface RegionOption {
  code: string;
  name: string;
}

export interface RegionGroup {
  country: string;
  options: RegionOption[];
}

export const REGION_GROUPS: RegionGroup[] = [
  {
    country: "Canada",
    options: [
      { code: "CA-AB", name: "Alberta" },
      { code: "CA-BC", name: "British Columbia" },
      { code: "CA-MB", name: "Manitoba" },
      { code: "CA-NB", name: "New Brunswick" },
      { code: "CA-NL", name: "Newfoundland and Labrador" },
      { code: "CA-NS", name: "Nova Scotia" },
      { code: "CA-NT", name: "Northwest Territories" },
      { code: "CA-NU", name: "Nunavut" },
      { code: "CA-ON", name: "Ontario" },
      { code: "CA-PE", name: "Prince Edward Island" },
      { code: "CA-QC", name: "Quebec" },
      { code: "CA-SK", name: "Saskatchewan" },
      { code: "CA-YT", name: "Yukon" },
    ],
  },
  {
    country: "United States",
    options: [
      { code: "US-AL", name: "Alabama" },
      { code: "US-AK", name: "Alaska" },
      { code: "US-AZ", name: "Arizona" },
      { code: "US-AR", name: "Arkansas" },
      { code: "US-CA", name: "California" },
      { code: "US-CO", name: "Colorado" },
      { code: "US-CT", name: "Connecticut" },
      { code: "US-DE", name: "Delaware" },
      { code: "US-DC", name: "District of Columbia" },
      { code: "US-FL", name: "Florida" },
      { code: "US-GA", name: "Georgia" },
      { code: "US-HI", name: "Hawaii" },
      { code: "US-ID", name: "Idaho" },
      { code: "US-IL", name: "Illinois" },
      { code: "US-IN", name: "Indiana" },
      { code: "US-IA", name: "Iowa" },
      { code: "US-KS", name: "Kansas" },
      { code: "US-KY", name: "Kentucky" },
      { code: "US-LA", name: "Louisiana" },
      { code: "US-ME", name: "Maine" },
      { code: "US-MD", name: "Maryland" },
      { code: "US-MA", name: "Massachusetts" },
      { code: "US-MI", name: "Michigan" },
      { code: "US-MN", name: "Minnesota" },
      { code: "US-MS", name: "Mississippi" },
      { code: "US-MO", name: "Missouri" },
      { code: "US-MT", name: "Montana" },
      { code: "US-NE", name: "Nebraska" },
      { code: "US-NV", name: "Nevada" },
      { code: "US-NH", name: "New Hampshire" },
      { code: "US-NJ", name: "New Jersey" },
      { code: "US-NM", name: "New Mexico" },
      { code: "US-NY", name: "New York" },
      { code: "US-NC", name: "North Carolina" },
      { code: "US-ND", name: "North Dakota" },
      { code: "US-OH", name: "Ohio" },
      { code: "US-OK", name: "Oklahoma" },
      { code: "US-OR", name: "Oregon" },
      { code: "US-PA", name: "Pennsylvania" },
      { code: "US-RI", name: "Rhode Island" },
      { code: "US-SC", name: "South Carolina" },
      { code: "US-SD", name: "South Dakota" },
      { code: "US-TN", name: "Tennessee" },
      { code: "US-TX", name: "Texas" },
      { code: "US-UT", name: "Utah" },
      { code: "US-VT", name: "Vermont" },
      { code: "US-VA", name: "Virginia" },
      { code: "US-WA", name: "Washington" },
      { code: "US-WV", name: "West Virginia" },
      { code: "US-WI", name: "Wisconsin" },
      { code: "US-WY", name: "Wyoming" },
    ],
  },
];
