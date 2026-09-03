import { Link } from "react-router-dom";
import { InvestigationForm } from "../components/InvestigationForm";

export function NewInvestigationPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <Link to="/investigations" className="text-sm text-gray-500 hover:text-gray-700">
          &larr; Back to Investigations
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-gray-900">New Investigation</h1>
        <p className="mt-1 text-sm text-gray-500">
          Create a new OSINT investigation by entering a target below.
        </p>
      </div>
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <InvestigationForm />
      </div>
    </div>
  );
}
