package completiondata

const SchemaVersion = 1

type Manifest struct {
	SchemaVersion int       `json:"schema_version"`
	Commands      []Command `json:"commands"`
	Modules       []string  `json:"modules"`
	GlobalOptions []Option  `json:"global_options"`
}

type Command struct {
	Name           string   `json:"name"`
	Description    string   `json:"description,omitempty"`
	Kind           string   `json:"kind"`
	AcceptsModules bool     `json:"accepts_modules,omitempty"`
	Options        []Option `json:"options,omitempty"`
}

type Option struct {
	Name   string   `json:"name"`
	Values []string `json:"values,omitempty"`
	File   bool     `json:"file,omitempty"`
}
