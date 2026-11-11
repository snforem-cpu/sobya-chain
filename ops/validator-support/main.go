// Standalone administrative service. Deliberately outside sobya/app and the
// consensus runtime. It has no chain transaction signer or write-RPC client.
package main

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type Application struct {
	ID string `json:"id"`
	OperatorName string `json:"operator_name"`
	Contact string `json:"contact"`
	AccountAddress string `json:"account_address"`
	ValidatorAddress string `json:"validator_address"`
	ConsensusPubKey string `json:"consensus_pubkey"`
	NodeEndpoint string `json:"node_endpoint"`
	SoftwareVersion string `json:"software_version"`
	Commission string `json:"commission"`
	Status string `json:"status"`
	RequestedAmount string `json:"requested_amount,omitempty"`
	ApprovedAmount string `json:"approved_amount,omitempty"`
	Notes string `json:"notes,omitempty"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
	Evidence []Evidence `json:"evidence,omitempty"`
	Tranches []Tranche `json:"tranches,omitempty"`
}

type Evidence struct {
	ObservedAt time.Time `json:"observed_at"`
	Source string `json:"source"`
	Height int64 `json:"height,omitempty"`
	SignedBlocks int64 `json:"signed_blocks,omitempty"`
	WindowBlocks int64 `json:"window_blocks,omitempty"`
	Bonded bool `json:"bonded"`
	Jailed bool `json:"jailed"`
	Notes string `json:"notes,omitempty"`
}

type Tranche struct {
	Amount string `json:"amount"`
	TxHash string `json:"tx_hash,omitempty"`
	Status string `json:"status"`
	RecordedAt time.Time `json:"recorded_at"`
}

type Store struct {
	mu sync.Mutex
	path string
	apps map[string]Application
}

func newID() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil { return "", err }
	return hex.EncodeToString(b), nil
}

func NewStore(path string) (*Store, error) {
	s := &Store{path: path, apps: map[string]Application{}}
	b, err := os.ReadFile(path)
	if err == nil {
		if err = json.Unmarshal(b, &s.apps); err != nil { return nil, fmt.Errorf("decode store: %w", err) }
		if s.apps == nil { s.apps = map[string]Application{} }
	} else if !errors.Is(err, os.ErrNotExist) { return nil, err }
	return s, nil
}

func (s *Store) saveLocked() error {
	b, err := json.MarshalIndent(s.apps, "", "  ")
	if err != nil { return err }
	if err = os.MkdirAll(filepath.Dir(s.path), 0700); err != nil { return err }
	tmp := s.path + ".tmp"
	if err = os.WriteFile(tmp, b, 0600); err != nil { return err }
	if err = os.Rename(tmp, s.path); err != nil { _ = os.Remove(tmp); return err }
	return nil
}

func (s *Store) create(a Application) (Application, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, old := range s.apps {
		if old.AccountAddress == a.AccountAddress { return Application{}, errors.New("an application already exists for this account") }
	}
	id, err := newID()
	if err != nil { return Application{}, err }
	now := time.Now().UTC()
	a.ID, a.Status, a.CreatedAt, a.UpdatedAt = id, "submitted", now, now
	s.apps[id] = a
	if err = s.saveLocked(); err != nil { delete(s.apps, id); return Application{}, err }
	return a, nil
}

func (s *Store) list() []Application {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]Application, 0, len(s.apps))
	for _, a := range s.apps { out = append(out, a) }
	return out
}

func (s *Store) approveGrant(id, amount, notes string, budget *big.Int) (Application, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if budget == nil || budget.Sign() <= 0 {
		return Application{}, errors.New("support budget is not configured")
	}
	requested, err := parseAmount(amount)
	if err != nil { return Application{}, err }
	a, ok := s.apps[id]
	if !ok { return Application{}, errors.New("application not found") }
	committed := new(big.Int)
	for otherID, other := range s.apps {
		if otherID == id { continue }
		if other.ApprovedAmount == "" { continue }
		n, parseErr := parseAmount(other.ApprovedAmount)
		if parseErr != nil { return Application{}, fmt.Errorf("existing approved grant for %s is invalid", otherID) }
		committed.Add(committed, n)
	}
	if new(big.Int).Add(committed, requested).Cmp(budget) > 0 {
		return Application{}, errors.New("approval exceeds the total program support budget")
	}
	old := a
	a.Status, a.ApprovedAmount, a.Notes = "approved", amount, notes
	a.UpdatedAt = time.Now().UTC()
	s.apps[id] = a
	if err = s.saveLocked(); err != nil { s.apps[id] = old; return Application{}, err }
	return a, nil
}

func (s *Store) budgetUsed() (*big.Int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	total := new(big.Int)
	for id, a := range s.apps {
		if a.ApprovedAmount == "" { continue }
		n, err := parseAmount(a.ApprovedAmount)
		if err != nil { return nil, fmt.Errorf("invalid approved grant for %s", id) }
		total.Add(total, n)
	}
	return total, nil
}

func (s *Store) mutate(id string, fn func(*Application) error) (Application, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	a, ok := s.apps[id]
	if !ok { return Application{}, errors.New("application not found") }
	old := a
	if err := fn(&a); err != nil { return Application{}, err }
	a.UpdatedAt = time.Now().UTC()
	s.apps[id] = a
	if err := s.saveLocked(); err != nil { s.apps[id] = old; return Application{}, err }
	return a, nil
}

// parseAmount accepts positive integer base-denomination units only.
func parseAmount(v string) (*big.Int, error) {
	if v == "" || strings.TrimSpace(v) != v { return nil, errors.New("amount must be a positive integer in base-denomination units") }
	n, ok := new(big.Int).SetString(v, 10)
	if !ok || n.Sign() <= 0 { return nil, errors.New("amount must be a positive integer in base-denomination units") }
	return n, nil
}

func allocatedAmount(a *Application) *big.Int {
	total := new(big.Int)
	for _, tranche := range a.Tranches {
		if n, err := parseAmount(tranche.Amount); err == nil { total.Add(total, n) }
	}
	return total
}

type Server struct { store *Store; token string; budget *big.Int }

func (sv *Server) admin(w http.ResponseWriter, r *http.Request) bool {
	if sv.token == "" { http.Error(w, "admin API disabled: ADMIN_TOKEN is required", http.StatusServiceUnavailable); return false }
	const prefix = "Bearer "
	header := r.Header.Get("Authorization")
	if !strings.HasPrefix(header, prefix) { http.Error(w, "unauthorized", http.StatusUnauthorized); return false }
	got := strings.TrimPrefix(header, prefix)
	if len(got) != len(sv.token) || subtle.ConstantTimeCompare([]byte(got), []byte(sv.token)) != 1 {
		http.Error(w, "unauthorized", http.StatusUnauthorized); return false
	}
	return true
}

func jsonOut(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func decode(r *http.Request, v any) error {
	d := json.NewDecoder(io.LimitReader(r.Body, 1<<20))
	d.DisallowUnknownFields()
	if err := d.Decode(v); err != nil { return err }
	var extra any
	if err := d.Decode(&extra); err != io.EOF { return errors.New("request must contain exactly one JSON value") }
	return nil
}

func (sv *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	switch {
	case r.Method == "GET" && r.URL.Path == "/health":
		jsonOut(w, 200, map[string]string{"status": "ok", "mode": "off-chain-admin-only"})
	case r.Method == "POST" && r.URL.Path == "/applications":
		var a Application
		if err := decode(r, &a); err != nil { http.Error(w, "invalid JSON application", 400); return }
		a.ID, a.Status, a.CreatedAt, a.UpdatedAt = "", "", time.Time{}, time.Time{}
		a.Evidence, a.Tranches = nil, nil
		if a.OperatorName == "" || a.Contact == "" || a.AccountAddress == "" || a.ConsensusPubKey == "" || a.NodeEndpoint == "" || a.SoftwareVersion == "" {
			http.Error(w, "missing required application fields", 400); return
		}
		if len(a.OperatorName) > 160 || len(a.Contact) > 320 || len(a.AccountAddress) > 160 || len(a.ValidatorAddress) > 160 || len(a.NodeEndpoint) > 300 || len(a.ConsensusPubKey) > 1000 || len(a.SoftwareVersion) > 100 || len(a.Commission) > 32 {
			http.Error(w, "field too long", 400); return
		}
		created, err := sv.store.create(a)
		if err != nil { http.Error(w, err.Error(), 409); return }
		jsonOut(w, 201, created)
	case r.Method == "GET" && r.URL.Path == "/admin/applications":
		if !sv.admin(w, r) { return }
		jsonOut(w, 200, sv.store.list())
	case strings.HasPrefix(r.URL.Path, "/admin/applications/"):
		if r.Method != "POST" { http.Error(w, "method not allowed", http.StatusMethodNotAllowed); return }
		if !sv.admin(w, r) { return }
		parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/admin/applications/"), "/")
		if len(parts) != 2 || parts[0] == "" { http.NotFound(w, r); return }
		id, action := parts[0], parts[1]
		var out Application
		var err error
		switch action {
		case "approve":
			var body struct { Amount string `json:"amount"`; Notes string `json:"notes"` }
			if err = decode(r, &body); err != nil { http.Error(w, "invalid approval payload", 400); return }
			if _, err = parseAmount(body.Amount); err != nil { http.Error(w, err.Error(), 400); return }
			out, err = sv.store.approveGrant(id, body.Amount, body.Notes, sv.budget)
		case "evidence":
			var ev Evidence
			if err = decode(r, &ev); err != nil { http.Error(w, "invalid evidence", 400); return }
			if ev.Source == "" || ev.ObservedAt.IsZero() || ev.Height < 0 || ev.WindowBlocks <= 0 || ev.SignedBlocks < 0 || ev.SignedBlocks > ev.WindowBlocks {
				http.Error(w, "invalid evidence fields", 400); return
			}
			out, err = sv.store.mutate(id, func(a *Application) error {
				if a.Status != "approved" && a.Status != "active" { return errors.New("application must be approved or active before monitoring") }
				a.Evidence = append(a.Evidence, ev)
				// Provisional 95% threshold; not a network consensus parameter.
				ratio := new(big.Int).Mul(big.NewInt(ev.SignedBlocks), big.NewInt(100))
				required := new(big.Int).Mul(big.NewInt(ev.WindowBlocks), big.NewInt(95))
				if ev.Bonded && !ev.Jailed && ratio.Cmp(required) >= 0 { a.Status = "active" } else { a.Status = "under_review" }
				return nil
			})
		case "tranches":
			var t Tranche
			if err = decode(r, &t); err != nil { http.Error(w, "invalid tranche payload", 400); return }
			amount, amountErr := parseAmount(t.Amount)
			if amountErr != nil || (t.Status != "planned" && t.Status != "paid" && t.Status != "withheld") {
				http.Error(w, "positive integer amount and valid status (planned|paid|withheld) are required", 400); return
			}
			if t.Status == "paid" && strings.TrimSpace(t.TxHash) == "" { http.Error(w, "paid tranche requires a transaction hash", 400); return }
			if len(t.TxHash) > 160 { http.Error(w, "transaction hash too long", 400); return }
			out, err = sv.store.mutate(id, func(a *Application) error {
				if a.Status != "approved" && a.Status != "active" && a.Status != "under_review" { return errors.New("application is not approved") }
				approved, e := parseAmount(a.ApprovedAmount)
				if e != nil { return errors.New("approved grant amount is invalid") }
				if new(big.Int).Add(allocatedAmount(a), amount).Cmp(approved) > 0 { return errors.New("tranche exceeds the approved grant amount") }
				for _, existing := range a.Tranches {
					if t.TxHash != "" && existing.TxHash == t.TxHash { return errors.New("transaction already recorded") }
				}
				t.RecordedAt = time.Now().UTC()
				a.Tranches = append(a.Tranches, t)
				return nil
			})
		case "complete":
			out, err = sv.store.mutate(id, func(a *Application) error {
				if a.Status != "active" { return errors.New("only active validators can complete") }
				a.Status = "completed"
				return nil
			})
		default:
			http.NotFound(w, r); return
		}
		if err != nil { http.Error(w, err.Error(), 409); return }
		jsonOut(w, 200, out)
	default:
		http.NotFound(w, r)
	}
}

func main() {
	path := os.Getenv("DATA_FILE")
	if path == "" { path = "./data/validator-support.json" }
	store, err := NewStore(path)
	if err != nil { panic(err) }
	budgetText := os.Getenv("SUPPORT_BUDGET_BASE_UNITS")
	budget, budgetErr := parseAmount(budgetText)
	if budgetErr != nil { panic("SUPPORT_BUDGET_BASE_UNITS must be set to a positive integer in base-denomination units") }
	addr := os.Getenv("LISTEN_ADDR")
	if addr == "" { addr = "127.0.0.1:8097" }
	s := &http.Server{Addr: addr, Handler: &Server{store: store, token: os.Getenv("ADMIN_TOKEN"), budget: budget}, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 60 * time.Second}
	fmt.Printf("validator-support listening on %s (off-chain only)\n", addr)
	if err = s.ListenAndServe(); err != nil && err != http.ErrServerClosed { panic(err) }
}
