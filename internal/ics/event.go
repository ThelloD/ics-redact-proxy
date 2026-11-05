package ics

import (
	"crypto/sha256"
	"encoding/hex"
	"slices"
	"strings"

	"gabe565.com/ics-redact-proxy/internal/config"
	ics "github.com/arran4/golang-ical"
)

func FilterComponent(conf *config.Config, c *ics.ComponentBase) {
	// Filter properties of the outer component, e.g. VEVENT.
	c.Properties = slices.DeleteFunc(c.Properties, func(property ics.IANAProperty) bool {
		return !slices.Contains(conf.ComponentFields, property.IANAToken)
	})
	c.Properties = slices.Clip(c.Properties)

	if conf.NewEventSummary != "" {
		c.SetSummary(conf.NewEventSummary)
	}

	if conf.HashUID {
		if uid := c.GetProperty(ics.ComponentPropertyUniqueId); uid != nil {
			checksum := sha256.Sum256([]byte(uid.Value))
			uid.Value = hex.EncodeToString(checksum[:])
		}
	}

	// Filter nested components such as VALARM.
	for _, child := range c.Components {
		switch alarm := child.(type) {
		case *ics.VAlarm:
			FilterAlarm(conf, alarm)
		}
	}
}

func FilterAlarm(conf *config.Config, alarm *ics.VAlarm) {
	// Remember the original action before filtering properties.
	action := ""
	if actionProp := alarm.GetProperty(ics.ComponentPropertyAction); actionProp != nil {
		action = strings.ToUpper(strings.TrimSpace(actionProp.Value))
	}

	// Keep only generic alarm properties that cannot contain private content.
	//
	// ACTION is re-added below so that we can normalize unsafe/unsupported
	// action types.
	allowedFields := []string{
		"TRIGGER",
		"DURATION",
		"REPEAT",
	}

	alarm.Properties = slices.DeleteFunc(alarm.Properties, func(property ics.IANAProperty) bool {
		return !slices.Contains(allowedFields, property.IANAToken)
	})
	alarm.Properties = slices.Clip(alarm.Properties)

	switch action {
	case "NONE":
		// Some calendar implementations use ACTION:NONE to represent
		// a disabled alarm. Preserve this semantics exactly.
		alarm.SetProperty(ics.ComponentPropertyAction, "NONE")

	case "AUDIO":
		// AUDIO only requires ACTION + TRIGGER.
		// ATTACH is optional and intentionally removed to avoid leaking
		// URLs or other data.
		alarm.SetAction(ics.ActionAudio)

	default:
		// For "DISPLAY", keep the original display-alarm semantics, but 
		// redact its text.
		
		// "EMAIL" requires SUMMARY, DESCRIPTION and ATTENDEE.
		// Unknown/vendor-specific actions may have similar requirements.
		// Normalize them to a simple local display alarm.
		alarm.SetAction(ics.ActionDisplay)
		alarm.SetDescription(privateAlarmDescription(conf))
	}
}

func privateAlarmDescription(conf *config.Config) string {
	if conf.NewEventSummary != "" {
		return conf.NewEventSummary
	}
	return "(private)"
}