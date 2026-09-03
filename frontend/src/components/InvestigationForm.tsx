import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { useCreateInvestigation } from "../hooks/useApi";
import type { InvestigationCreate } from "../api/investigations";

const formSchema = z.object({
  name: z.string().min(1, "Name is required").max(200),
  target: z.string().min(1, "Target is required").max(500),
  depth: z.enum(["shallow", "standard", "deep"]),
});

type FormData = z.infer<typeof formSchema>;

const depthOptions = [
  { value: "shallow", label: "Shallow", desc: "Quick scan, minimal API calls" },
  { value: "standard", label: "Standard", desc: "Balanced depth and cost" },
  { value: "deep", label: "Deep", desc: "Thorough, uses full budget" },
] as const;

export function InvestigationForm() {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema) as never,
    defaultValues: { depth: "standard" },
  });

  const mutation = useCreateInvestigation();

  const onSubmit = (data: FormData) => {
    const payload: InvestigationCreate = {
      name: data.name,
      target: data.target,
      depth: data.depth,
    };
    mutation.mutate(payload, {
      onSuccess: () => navigate("/investigations"),
    });
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-gray-700">
          Investigation Name
        </label>
        <input
          id="name"
          type="text"
          {...register("name")}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="e.g. Example Corp Recon"
        />
        {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>}
      </div>

      <div>
        <label htmlFor="target" className="block text-sm font-medium text-gray-700">
          Target
        </label>
        <input
          id="target"
          type="text"
          {...register("target")}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="e.g. example.com, 8.8.8.8, user@domain.com"
        />
        <p className="mt-1 text-xs text-gray-500">Domain, IP address, URL, email, or username</p>
        {errors.target && <p className="mt-1 text-sm text-red-600">{errors.target.message}</p>}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Depth</label>
        <div className="mt-2 grid grid-cols-3 gap-3">
          {depthOptions.map((opt) => (
            <label
              key={opt.value}
              className="relative flex cursor-pointer flex-col items-center rounded-md border border-gray-300 p-3 text-center hover:border-blue-400 has-[:checked]:border-blue-500 has-[:checked]:bg-blue-50"
            >
              <input type="radio" value={opt.value} {...register("depth")} className="sr-only" />
              <span className="text-sm font-medium text-gray-900">{opt.label}</span>
              <span className="mt-1 text-xs text-gray-500">{opt.desc}</span>
            </label>
          ))}
        </div>
      </div>

      {mutation.isError && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {mutation.error.message}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
        >
          {mutation.isPending ? "Creating..." : "Create Investigation"}
        </button>
        <button
          type="button"
          onClick={() => navigate("/investigations")}
          className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
