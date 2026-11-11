package main

import (
	"bytes"
	"encoding/json"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"
)

func testServer(t *testing.T) *Server {
	t.Helper()
	s, e := NewStore(filepath.Join(t.TempDir(), "state.json"))
	if e != nil {
		t.Fatal(e)
	}
	return &Server{store: s, token: "test-secret"}
}

func request(s *Server, method, path, body string, admin bool) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, path, bytes.NewBufferString(body))
	if admin {
		r.Header.Set("Authorization", "Bearer test-secret")
	}
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	return w
}

func TestCreateAndDuplicateApplication(t *testing.T) {
	s := testServer(t)
	body := `{"operator_name":"Node A","contact":"ops@example.test","account_address":"sobya1abc","consensus_pubkey":"pub","node_endpoint":"node.example:26656","software_version":"v0.1.0"}`
	if w := request(s, "POST", "/applications", body, false); w.Code != 201 {
		t.Fatalf("create: %d %s", w.Code, w.Body)
	}
	if w := request(s, "POST", "/applications", body, false); w.Code != 409 {
		t.Fatalf("duplicate: %d", w.Code)
	}
}

func TestApprovalEvidenceAndStagedTranche(t *testing.T) {
	s := testServer(t)
	a, e := s.store.create(Application{OperatorName: "Node B", Contact: "ops@example.test", AccountAddress: "sobya1b", ConsensusPubKey: "pub", NodeEndpoint: "node:26656", SoftwareVersion: "v1"})
	if e != nil {
		t.Fatal(e)
	}
	path := "/admin/applications/" + a.ID
	if w := request(s, "POST", path+"/approve", `{"amount":"1000000000000000000","notes":"stage 1"}`, true); w.Code != 200 {
		t.Fatalf("approve: %d %s", w.Code, w.Body)
	}
	ev := Evidence{ObservedAt: time.Now().UTC(), Source: "manual RPC snapshot", Height: 10, SignedBlocks: 96, WindowBlocks: 100, Bonded: true}
	b, _ := json.Marshal(ev)
	if w := request(s, "POST", path+"/evidence", string(b), true); w.Code != 200 {
		t.Fatalf("evidence: %d %s", w.Code, w.Body)
	}
	tr := `{"amount":"500000000000000000","tx_hash":"ABC123","status":"paid"}`
	if w := request(s, "POST", path+"/tranches", tr, true); w.Code != 200 {
		t.Fatalf("tranche: %d %s", w.Code, w.Body)
	}
	if w := request(s, "POST", path+"/tranches", tr, true); w.Code != 409 {
		t.Fatalf("duplicate tx: %d", w.Code)
	}
}

func TestAdminAuthAndNoRPCWriteSurface(t *testing.T) {
	s := testServer(t)
	if w := request(s, "GET", "/admin/applications", "", false); w.Code != 401 {
		t.Fatalf("unauthenticated admin: %d", w.Code)
	}
	if w := request(s, "POST", "/broadcast", "{}", true); w.Code != 404 {
		t.Fatalf("unexpected broadcast route: %d", w.Code)
	}
}

func TestPersistence(t *testing.T) {
	p := filepath.Join(t.TempDir(), "state.json")
	s, e := NewStore(p)
	if e != nil {
		t.Fatal(e)
	}
	_, e = s.create(Application{OperatorName: "Persist", Contact: "x", AccountAddress: "a1", ConsensusPubKey: "p", NodeEndpoint: "n", SoftwareVersion: "v"})
	if e != nil {
		t.Fatal(e)
	}
	s2, e := NewStore(p)
	if e != nil {
		t.Fatal(e)
	}
	if len(s2.list()) != 1 {
		t.Fatal("application was not persisted")
	}
}
